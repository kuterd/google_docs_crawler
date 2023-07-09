program_desc = """
    A crawler for Google Docs.

    For a given list of seed documents, this crawler will BFS crawl all linked documents recursively and
    attempt to find the titles of the documents.

    Currently only publicly available documents are supported.
"""

from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse, parse_qs
from argparse import ArgumentParser
import csv
import re
import sys
import os
import string
import concurrent
from concurrent.futures import ThreadPoolExecutor

parser = ArgumentParser(description=program_desc)
parser.add_argument(
    "seeds", metavar="S", nargs="+", help="Seed documents to start from"
)
parser.add_argument(
    "--max-depth",
    type=int,
    default=sys.maxsize,
    help="Maximum depth that the crawler will reach",
)
parser.add_argument("-o", "--output", default="report.csv", help="CSV report file"),
parser.add_argument(
    "--allow-speculative-title-detection",
    type=bool,
    default=True,
    help="Allow speculative detection of document titles",
)
parser.add_argument(
    "--download-folder",
    type=str,
    default=None,
    help="If specified, will save the html contents to a folder",
)
parser.add_argument(
    "--max-workers",
    type=int,
    default=4,  # A large number here may create too much load.
    help="Maximum number of worker threads to use.",
)
parser.add_argument("--crawl-slides", type=bool, default=True, help="Include Google Docs in crawl")

args = parser.parse_args()

threadpool = ThreadPoolExecutor(max_workers=args.max_workers)

DOCS_BASE = "https://docs.google.com/document/d/"
SLIDES_BASE = "https://docs.google.com/presentation/d/"
DOCS_REGEX = f"^{DOCS_BASE}([^/#]*)"
SLIDES_REGEX = f"^{SLIDES_BASE}([^/#]*)"

SLIDES = "slides"
DOCUMENT = "document"

# To be able to reuse the connection.
session = requests.Session()


def docs_html_from_id(did):
    """
    For a given Google docs document id get the url for html export.
    """
    return f"https://docs.google.com/feeds/download/documents/export/Export?id={did}&exportFormat=html"

def slide_html_from_id(did):
    return f"https://docs.google.com/presentation/d/{did}/htmlpresent"

def un_google_url(url):
    """
    Remove the Google redirect.
    """
    #FIXME: Make this more safu for against non redirect urls. 
    parsed = urlparse(url)
    if parsed.hostname != "www.google.com":
        return url
    query_params = parse_qs(parsed.query)
    if "q" not in query_params:
        return url
    return query_params["q"][0]


def document_id_from_url(url):
    """
    Extract the document id from a document link.
    """
    match = re.match(DOCS_REGEX, url)
    if match == None:
        return None
    return match.group(1)

def slides_id_from_url(url):
    """
    Extract the document id from a document link.
    """
    match = re.match(SLIDES_REGEX, url)
    if match == None:
        return None
    return match.group(1)

def fetch_document_by_id(did):
    """
    Fetch the html contents of a document given a document id.
    """
    response = session.get(docs_html_from_id(did), allow_redirects=False)
    if response.status_code != 200:
        return None

    return response.text

def fetch_slides_by_id(did):
    response = session.get(slide_html_from_id(did), allow_redirects=False)
    if response.status_code != 200:
        return None

    return response.text


def find_document_title(dom):
    """
    Attempt to extract the document id from the document html dom.
    """
    #NOTE: Do we want to have different handling for slides ?
    element = dom.find(class_="title")
    if element:
        return element.get_text()

    # Should this be the default way of handling titles ?
    element = dom.find("title")
    if element:
        title_raw = element.get_text()
        match = re.match("(.*) - Google [^- ]*", title_raw)
        if not match:
            return title_raw
        return match.group(1)

    if not args.allow_speculative_title_detection:
        return None

    element = dom.find("h1")
    if element:
        return element.get_text()

    element = dom.find("h2")
    if element:
        return element.get_text()

    return None

def title_slug(title):
    title = title.lower()
    title = title.replace(" ", "-")
    return re.sub("[^" + string.ascii_letters + string.digits + "-]", "", title)


def find_links(dom):
    """
    Extract and un google links inside a dom.
    """
    anchors = dom.find_all("a")
    result = []
    for anchor in anchors:
        href = anchor.get("href")
        if href == None:
            continue
        result.append(un_google_url(href))
    return result


class Crawler:
    def __init__(self, seeds):
        # Document ids to explore.
        self.to_explore = set()
        # Documents already explored.
        self.explored = set()
        self.results = []
        for seed in seeds:
            item = self.item_from_url(seed)
            if item:
                self.to_explore.add(item)

    def item_from_url(self, url):
        did = document_id_from_url(url)
        if did:
            return (DOCUMENT, did)
        if args.crawl_slides:
            did = slides_id_from_url(url)
            if did:
                return (SLIDES, did)
        return None
    
    def item_to_url(self, item):
        if item[0] == DOCUMENT:
            return DOCS_BASE + item[1]
        elif item[1] == SLIDES:
            return SLIDES_BASE + item[1]
        return None
    
    def _single_fetch(self, item):
        found = set()
        try:
            contents = None
            if item[0] == DOCUMENT:
                contents = fetch_document_by_id(item[1])
            elif item[0] == SLIDES:
                contents = fetch_slides_by_id(item[1])

            if not contents:
                # TODO: Maybe log something when this happens ?
                return found
            dom = BeautifulSoup(contents, "html.parser")
            title = find_document_title(dom)
            title = title if title else "No Title"

            print("Document title:", title)
            # print("slug", title_slug(title))

            if args.download_folder:
                result = os.path.join(
                    args.download_folder, title_slug(title) + f"_{item[1]}.html"
                )
                file = open(result, "w")
                file.write(contents)
                file.close()

            self.results.append((title, self.item_to_url(item)))

            links = find_links(dom)
            for link in links:
                item = self.item_from_url(link)
                if item and item not in self.explored:
                    found.add(item)
        except Exception as e:
            print("Exception", e, "occured while processing", item, "skiping")
        return found

    def expand(self):
        """
        Expand the BFS search.
        """
        print(len(self.to_explore), "documents to search")
        found = set()
        scrape_futures = []
        for item in self.to_explore:
            self.explored.add(item)
            scrape_futures.append(threadpool.submit(self._single_fetch, item))

        for future in scrape_futures:
            try:
                scrape_found = future.result()
                found |= scrape_found
            except Exception as e:
                print("exception while fetching result.", e)

        self.to_explore = found
        return len(self.to_explore) > 0

    def write_report(self, filename):
        """
        Write the report as a csv file.
        """
        result_file = open(filename, "w")
        writer = csv.writer(result_file)
        writer.writerow(["title", "link"])
        for result in crawler.results:
            writer.writerow(result)


crawler = Crawler(args.seeds)

for i in range(args.max_depth):
    if not crawler.expand():
        # No more documents to explore.
        break

crawler.write_report(args.output)
