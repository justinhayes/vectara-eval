# vectara-eval
A project that shows how to do a Vectara search evaluation on a specific data set. The script does the following:
1. creates a corpus and uploads data to be indexed (if not already done)
2. runs test queries
3. calculates metrics and stores them in the results directory

Each test case is organized into a 'bundle', which consists of one or more data files and a file containing test 
queries. Each test query has one or more expected matches (from amongst the data files), which are used to determine 
how well the search performed.

The script can be run via the following commands:
```
python3 run_eval.py \
    --auth-url "<COPY FROM VECTARA CONSOLE>" \
    --app-client-id "<COPY FROM VECTARA CONSOLE>" \
    --app-client-secret "<COPY FROM VECTARA CONSOLE>" \
    --customer-id <COPY FROM VECTARA CONSOLE> \
    --bundle <ONE OF [doc-search | faq-search | app-search]> \
    --corpus-id <COPY FROM VECTARA CONSOLE>
```

If the corpus-id argument is included then that tells the script to not create a new corpus and upload all the data 
files for this bundle, and instead to run the searches against the existing corpus.

Please note that the identified matches for each test query in the queries.csv files are there for demonstration
purposes only. They were chosen to illustrate the concepts related to search system evaluations.
They do not represent an exhaustive set of matches for each query. Therefore, the actual search results
will include matches that are not listed in the respective queries.csv files, and the corresponding relevance metrics
will reflect that. Put another way, do not read anything into the relevance metrics generated by this test project.

That said, if you create your own bundle for testing purposes, you should select your test queries and specify the 
corresponding matches such that they **are** exhaustive of all relevant matches. Doing that will ensure that you get 
an accurate understanding of what type of relevance Vectara can provide for your use case.

Disclaimers:
* The data in the doc-search bundle was copied from the UNFCC secretariat website (https://unfccc.int/documents, https://unfccc.int/this-site/terms-of-use). The data files are documents submitted to the UN related to the initiatives different countries have related to climate change emissions reductions.
* The data in the app-search bundle comes from the OpinRank data set (https://github.com/kavgan/OpinRank, http://kavita-ganesan.com/entity-ranking-data/#.Y74GmeLMKOA). Ganesan, K. A., and C. X. Zhai, “Opinion-Based Entity Ranking“, Information Retrieval.