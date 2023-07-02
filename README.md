# Google docs crawler

This is a tool for recursively crawling Google Docs.

We use the html export functionality of Google Docs to retrieve the html format of the document,
then we find other docs that it links to, and so on, until the `--max-depth` is reached.


```
usage: main.py [-h] [--max-depth MAX_DEPTH] [-o OUTPUT] [--allow-speculative-title-detection ALLOW_SPECULATIVE_TITLE_DETECTION] [--download-folder DOWNLOAD_FOLDER] S [S ...]

A crawler for Google Docs. For a given list of seed documents, this crawler will BFS crawl all linked documents recursively and attempt to find the titles of the documents. Currently only publicly available documents are supported.

positional arguments:
  S                     Seed documents to start from

options:
  -h, --help            show this help message and exit
  --max-depth MAX_DEPTH
                        Maximum depth that the crawler will reach
  -o OUTPUT, --output OUTPUT
                        CSV report file
  --allow-speculative-title-detection ALLOW_SPECULATIVE_TITLE_DETECTION
                        Allow speculative detection of document titles
  --download-folder DOWNLOAD_FOLDER
                        If specified, will save the html contents to a folder
```
