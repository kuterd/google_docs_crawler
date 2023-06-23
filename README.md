# Google docs crawler

This is a very simple Google documents crawler. 

We use the html export endpoint of Google documents to find links to other documents.


```
usage: main.py [-h] [--max-depth MAX_DEPTH] [-o OUTPUT] S [S ...]

A crawler for Google Docs. For a given list of seed documents, this crawler will BFS crawl all linked documents recursively and attempt to find the titles of the documents. Currently only publicly available documents are supported.

positional arguments:
  S                     Seed documents to start from

options:
  -h, --help            show this help message and exit
  --max-depth MAX_DEPTH
                        Maximum depth that the crawler will reach
  -o OUTPUT, --output OUTPUT
                        CSV report file
```
