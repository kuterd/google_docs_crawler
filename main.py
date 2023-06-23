program_desc  = """
    A crawler for Google Docs.

    For a given list of seed documents, this crawler will BFS crawl all linked documents recursively and
    attempt to find the titles of the documents.\n\n

    Currently only publicly available documents are supported.
"""

from bs4 import BeautifulSoup
import requests

from urllib.parse import urlparse, parse_qs
from argparse import ArgumentParser
import csv
import re
import sys

parser = ArgumentParser(description=program_desc)
parser.add_argument("seeds", metavar="S", nargs="+", help="Seed documents to start from")
parser.add_argument("--max-depth", type=int, default=sys.maxsize, help="Maximum depth that the crawler will reach")
parser.add_argument("-o", "--output", default="report.csv", help="CSV report file"),

args = parser.parse_args()

DOCS_BASE = "https://docs.google.com/document/d/"
DOCS_REGEX = f"^{DOCS_BASE}([^/#]*)"

# To be able to reuse the connection.
session = requests.Session()

"""
    For a given Google docs document id get the url for html export.
"""
def html_url_from_id(did):
    return f"https://docs.google.com/feeds/download/documents/export/Export?id={did}&exportFormat=html"

"""
    Remove the Google redirect.
"""
def un_google_url(url):
    parsed = urlparse(url)
    if parsed.hostname != "www.google.com":
        return url
    query_params = parse_qs(parsed.query)
    if "q" not in query_params:
        return url
    return query_params["q"][0]


"""
    Extract the document id from a document link.
"""
def document_id_from_url(url):
    match = re.match(DOCS_REGEX, url)
    if match == None:
        return None
    return match.group(1) 

"""
    Fetch the html contents of a document given a document id.
"""
def fetch_document_by_id(did):
    response = session.get(html_url_from_id(did), allow_redirects=False)
    if response.status_code != 200:
        return None

    return response.text

"""
    Attempt to extract the document id from the document html dom.
"""
def find_document_title(dom):
    element = dom.find(class_="title")
    if element:
        return element.get_text()
    return "No title"

"""
    Extract and un google links inside a dom.
"""
def find_links(dom):
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
            did = document_id_from_url(seed)
            self.to_explore.add(did)

    """
        Expand the BFS search.
    """
    def expand(self):
        print(len(self.to_explore), "documents to search")
        found = set()
        for did in self.to_explore:
            self.explored.add(did)
            contents = fetch_document_by_id(did)
            if not contents:
                continue
            dom = BeautifulSoup(contents, "html.parser")
            title = find_document_title(dom)
            print("Document title:", title)
            
            self.results.append((title, DOCS_BASE + did)) 

            links = find_links(dom)
            for link in links:
                ldid = document_id_from_url(link)
                if ldid and ldid not in self.explored:
                    found.add(ldid)
        self.to_explore = found
        return len(self.to_explore) > 0

    """
        Write the report as a csv file.
    """
    def write_report(self, filename):
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
