# vectara-eval
A project that shows how to do a Vectara search evaluation on a specific data set. The script does the following:
1. creates a corpus and uploads data to be indexed (if not already done)
2. runs test queries
3. calculates metrics and stores them in the results directory

Each test case is organized into a 'bundle', which consists of one or more data files and a file containing test queries. Each test query has one or more expected matches (from amongst the data files), which are used to determine how well the search performed.

The script can be run via the following commands:
```
python3 run_eval.py \
    --auth-url "<COPY FROM VECTARA CONSOLE>" \
    --app-client-id "<COPY FROM VECTARA CONSOLE>" \
    --app-client-secret "<COPY FROM VECTARA CONSOLE>" \
    --customer-id <COPY FROM VECTARA CONSOLE> \
    --bundle <ONE OF [doc-search | faq-search | transcript-search]> \
    --corpus-id <COPY FROM VECTARA CONSOLE>
```

If the corpus-id argument is included then that tells the script to not create a new corpus and upload all the data files for this bundle, and instead to run the searches against the existing corpus.
