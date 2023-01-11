""" This is a project that gives an example of how to do an evaluation of the Vectara platform.
It calls the Vectara API via python using HTTP/REST as communication protocol.
"""

import argparse
import logging
import datetime
import json
import requests
import os
import sys
from authlib.integrations.requests_client import OAuth2Session

def _get_jwt_token(auth_url: str, app_client_id: str, app_client_secret: str):
    """Connect to the server and get a JWT token."""
    token_endpoint = f"{auth_url}/oauth2/token"
    session = OAuth2Session(
        app_client_id, app_client_secret, scope="")
    token = session.fetch_token(token_endpoint, grant_type="client_credentials")
    return token["access_token"]

def _get_create_corpus_json(bundle: str):
    """ Returns a create corpus json.
    Args:
         bundle: Which test bundle is being used this run

    Returns:
        JSON string that can be used in a create corpus request
    """

    corpus = {}
    corpus["name"] = bundle + " eval - " + \
                     datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    corpus["description"] = "A corpus to execute a Vectara evaluation."

    return json.dumps({"corpus":corpus})

def create_corpus(customer_id: int, admin_address: str, jwt_token: str, bundle: str):
    """Create a corpus.
    Args:
        customer_id: Unique customer ID in vectara platform.
        admin_address: Address of the admin server. e.g., admin.vectara.io
        jwt_token: A valid Auth token.
        bundle: Which test bundle is being used this run

    Returns:
        (response, True) in case of success and returns (error, False) in case of failure.
    """

    post_headers = {
        "customer-id": f"{customer_id}",
        "Authorization": f"Bearer {jwt_token}"
    }
    response = requests.post(
        f"https://h.{admin_address}/v1/create-corpus",
        data=_get_create_corpus_json(bundle),
        verify=True,
        headers=post_headers)

    if response.status_code != 200:
        logging.error("Create Corpus failed with code %d, reason %s, text %s",
                       response.status_code,
                       response.reason,
                       response.text)
        return response, False, ""

    #Get ID of corpus we just created
    corpus_id = json.loads(response.text).get('corpusId')

    return response, True, corpus_id

def upload_file(customer_id: int, corpus_id: int, idx_address: str, filepath: str, jwt_token: str):
    """ Uploads a file to the corpus.
    Args:
        customer_id: Unique customer ID in vectara platform.
        corpus_id: ID of the corpus to which data needs to be indexed.
        idx_address: Address of the indexing server. e.g., indexing.vectara.io
        filepath: Path to a file to be uploaded to the indexing service
        jwt_token: A valid Auth token.

    Returns:
        (response, True) in case of success and returns (error, False) in case of failure.
    """

    post_headers = {
        "Authorization": f"Bearer {jwt_token}"
    }

    #File being posted and also a custom metadata attribute called 'filepath' with the
    #path from which the file was loaded.

    #Build the dictionary that will contain all the metadata fields.
    doc_metadata = {"filepath": f"{filepath}"}
    #Encode it into a well-formatted JSON string
    doc_metadata_json = json.dumps(doc_metadata)
    #Create the dictionary that stores the file being uploaded and also the metadata field
    files={"file": (filepath, open(filepath, 'rb')), "doc_metadata": f"{doc_metadata_json}"}

    #Send the request
    response = requests.post(
        f"https://h.{idx_address}/upload?c={customer_id}&o={corpus_id}",
        files=files,
        verify=True,
        headers=post_headers)

    if response.status_code != 200:
        logging.error("REST upload failed with code %d, reason %s, text %s",
                       response.status_code,
                       response.reason,
                       response.text)
        return response, False
    return response, True

def upload_data(customer_id: int, corpus_id: int, idx_address: str, dirpath: str, jwt_token: str):
    """ Uploads a file to the corpus.
    Args:
        customer_id: Unique customer ID in vectara platform.
        corpus_id: ID of the corpus to which data needs to be indexed.
        idx_address: Address of the indexing server. e.g., indexing.vectara.io
        dirpath: Path to a directory containing files (and nested directories) to be uploaded to the indexing service
        jwt_token: A valid Auth token.

    Returns:
        (response, True) in case of success and returns (error, False) in case of failure.
    """
    
    responses = {}

    #Walk through the directory and all nested directories, and upload each file found
    for subdir, dirs, files in os.walk(dirpath):
        for file in files:
            filepath = os.path.join(subdir, file)
            print('\nUploading ' + filepath + '...')
            response, status = upload_file(customer_id,
                                      corpus_id,
                                      idx_address,
                                      filepath,
                                      jwt_token)
            logging.info("Upload File response: %s", response.text)
            responses[filepath] = response
            print('Uploaded ' + filepath)
    
    return responses, True

def _get_queries_list(queries_file: str):
    """This parses the queries.csv file into a data structure that contains all the
    queries to be run and the expected matches.

    Args:
        queries_file: Path to the file containing the queries to run in this evaluation.
            Each line represents one query in a pipe-separated list, with the following format:
                query_number|query_text|[matching_file_num@matching_file_phrase]+
            'query_number' should start with 1 and increase by one for each query
            'query_text' can be any query, but it cannot contain a pipe (|)
            'matching_file_num' must correspond to the prefix number of a file in this bundle's data directory that
                should be returned as a match for this query
            'matching_file_phrase' is a short phrase (e.g. 5-8 words) in the matching file that should be matched
            There can be one or more 'matching_file_num@matching_file_phrase' items, each separated by a pipe.
            An example line from this file is:
                1|where is the best barbecue?|27@best bbq is in Clemmons, NC|8@world's top brisket in Texas
            In this example there are two expected matches, one in the file that starts with "27-" (at the text that
            mentions Clemmons, and one in the file that starts with "8-" (at the text that mentions brisket).

    Returns:
        Array of dicts, each one representing a query to be executed, and having type
        {num:int, query:str, matches:[{file-num:str, phrase:str}]}
    """

    file_handle = open(queries_file, 'r')
    lines = file_handle.readlines()
    queries = []
    for line in lines:
        fields = line.split('|')
        if len(fields) < 3:
            continue
        this_query = {}
        this_query["num"] = int(fields[0])
        this_query["query"] = fields[1]
        this_query["matches"] = [{}] * (len(fields) - 2)
        for i in range(2, len(fields)):
            matches = fields[i].split('@')
            this_query["matches"][i-2] = {}
            this_query["matches"][i-2]["file-num"] = matches[0]
            this_query["matches"][i-2]["phrase"] = matches[1].strip()
        queries.append(this_query)
    file_handle.close()

    return queries

def _get_query_json(customer_id: int, corpus_id: int, query_text: str):
    """ Returns a query JSON string.

    Args:
        customer_id: Unique customer ID in vectara platform.
        corpus_id: ID of the corpus that will be searched.
        query_text: The query to be run.

    Returns:
        JSON string that can be used to execute the query
    """
    query = {}
    query_obj = {}

    query_obj["query"] = query_text
    query_obj["num_results"] = 100

    corpus_key = {}
    corpus_key["customer_id"] = customer_id
    corpus_key["corpus_id"] = corpus_id

    query_obj["corpus_key"] = [ corpus_key ]
    query["query"] = [ query_obj ]
    return json.dumps(query)

def _run_query(customer_id: int, corpus_id: int, query_address: str, jwt_token: str, this_query: {}):
    """ Runs a query in the Vectara platform.

    Args:
        customer_id: Unique customer ID in vectara platform.
        corpus_id: ID of the corpus that will be searched.
        query_address: Address of the querying service. e.g., serving.vectara.io
        jwt_token: A valid Auth token.
        this_query: A dict representing a single query (see _get_queries_list() for the format)

    Returns:
        (response, True) in case of success and returns (error, False) in case of failure.

    """
    post_headers = {
        "customer-id": f"{customer_id}",
        "Authorization": f"Bearer {jwt_token}"
    }

    # Send the request
    response = requests.post(
        f"https://h.{query_address}/v1/query",
        data=_get_query_json(customer_id, corpus_id, this_query["query"]),
        verify=True,
        headers=post_headers)

    if response.status_code != 200:
        logging.error("Query failed with code %d, reason %s, text %s",
                       response.status_code,
                       response.reason,
                       response.text)
    return response

def strings_overlap(str1: str, str2: str):
    """ Determines whether two strings overlap (case insensitively)

    Args:
        str1: first string
        str2: second string

    Returns:
        False if either string is None. True if one string contains the other string. False otherwise.
    """

    """
    DEFGHIJ & ABC   False   OK
    DEFGHIJ & BCD   True    NO
    DEFGHIJ & EFG   True    OK
    DEFGHIJ & IJK   True    NO
    DEFGHIJ & BCDEFGHIJ   True  OK
    DEFGHIJ & DEFGHIJKL   True  OK
    DEFGHIJ & BCDEFGHIJKL   True    OK
    """

    str1 = str1.lower()
    str2 = str2.lower()

    if str1 is None or str2 is None:
        return False

    if str1.find(str2) != -1 or str2.find(str1) != -1:
        return True

    return False

def compute_metrics(num_matches_on_file_top_1:[[]], num_matches_on_file_top_3:[[]],
                    num_matches_on_file_top_5:[[]], num_matches_on_file_top_10:[[]],
                    num_matches_on_file_and_phrase_top_1:[], num_matches_on_file_and_phrase_top_3:[],
                    num_matches_on_file_and_phrase_top_5:[], num_matches_on_file_and_phrase_top_10:[],
                    first_matches_on_file: [], first_matches_on_file_and_phrase:[]):
    """ Computes various metrics quantifying how this test run executed. Each input is an array that contains
     raw data corresponding to one metric for each query. Each of these arrays have a length the same as the
     total number of queries that were executed in the test.

    Args:
        num_matches_on_file_top_1: array of arrays of size 1 where each item is 0 if the corresponding
            result number for that query was a match (based only on the file)
        num_matches_on_file_top_3: array of arrays of size 3 where each item is 0 if the corresponding
            result number for that query was a match (based only on the file)
        num_matches_on_file_top_5: array of arrays of size 5 where each item is 0 if the corresponding
            result number for that query was a match (based only on the file)
        num_matches_on_file_top_10: array of arrays of size 10 where each item is 0 if the corresponding
            result number for that query was a match (based only on the file)
        num_matches_on_file_and_phrase_top_1: array of ints where each item is the number of results in
            the top 1 for that query that represented a match (based on both the file and the phrase)
        num_matches_on_file_and_phrase_top_3: array of ints where each item is the number of results in
            the top 3 for that query that represented a match (based on both the file and the phrase)
        num_matches_on_file_and_phrase_top_5: array of ints where each item is the number of results in
            the top 5 for that query that represented a match (based on both the file and the phrase)
        num_matches_on_file_and_phrase_top_10: array of ints where each item is the number of results in
            the top 10 for that query that represented a match (based on both the file and the phrase)
        first_matches_on_file: array of ints where each value is the result number where
            that query's first match (based only on the file) was found
        first_matches_on_file_and_phrase: array of ints where each value is the result number where
            that query's first match (based on both the file and the phrase) was found


    Returns:
        Dict where each item represents a metric type and its corresponding value
    """

    metrics = {}

    """
    print('num_matches_on_file_top_1=' + str(num_matches_on_file_top_1))
    print('num_matches_on_file_top_3=' + str(num_matches_on_file_top_3))
    print('num_matches_on_file_top_5=' + str(num_matches_on_file_top_5))
    print('num_matches_on_file_top_10=' + str(num_matches_on_file_top_10))
    print('num_matches_on_file_and_phrase_top_1=' + str(num_matches_on_file_and_phrase_top_1))
    print('num_matches_on_file_and_phrase_top_3=' + str(num_matches_on_file_and_phrase_top_3))
    print('num_matches_on_file_and_phrase_top_5=' + str(num_matches_on_file_and_phrase_top_5))
    print('num_matches_on_file_and_phrase_top_10=' + str(num_matches_on_file_and_phrase_top_10))
    print('first_matches_on_file=' + str(first_matches_on_file))
    print('first_matches_on_file_and_phrase=' + str(first_matches_on_file_and_phrase))
    """

    #Relevance @ K metrics for matches based only on identifying the target file.
    #Each of these metrics is the mean, across all test queries, of how many results in the top K represent
    #a relevant match. For example, file_match_mean_r_at_5=.6 indicates that across all test queries, the average
    #number of relevant matches within the first 5 search results was 3 (i.e. 60% of the top 5 results were relevant).
    metrics["file_match_mean_r_at_1"] = \
        sum(map(lambda n: sum(n) / 1, num_matches_on_file_top_1)) / len(num_matches_on_file_top_1)
    metrics["file_match_mean_r_at_3"] = \
        sum(map(lambda n: sum(n) / 3, num_matches_on_file_top_3)) / len(num_matches_on_file_top_3)
    metrics["file_match_mean_r_at_5"] = \
        sum(map(lambda n: sum(n) / 5, num_matches_on_file_top_5)) / len(num_matches_on_file_top_5)
    metrics["file_match_mean_r_at_10"] = \
        sum(map(lambda n: sum(n) / 10, num_matches_on_file_top_10)) / len(num_matches_on_file_top_10)

    #Relevance @ K metrics for matches based on identifying the target file and also the relevant phrase.
    #Each of these metrics is the mean, across all test queries, of how many results in the top K represent a relevant
    #match. For example, file_and_phrase_match_mean_r_at_10=.4 indicates that across all test queries, the average
    #number of relevant matches within the first 10 search results was 4 (i.e. 40% of the top 10 results were relevant).
    metrics["file_and_phrase_match_mean_r_at_1"] = \
        sum(map(lambda n: n / 1, num_matches_on_file_and_phrase_top_1)) / len(num_matches_on_file_and_phrase_top_1)
    metrics["file_and_phrase_match_mean_r_at_3"] = \
        sum(map(lambda n: n / 3, num_matches_on_file_and_phrase_top_3)) / len(num_matches_on_file_and_phrase_top_3)
    metrics["file_and_phrase_match_mean_r_at_5"] = \
        sum(map(lambda n: n / 5, num_matches_on_file_and_phrase_top_5)) / len(num_matches_on_file_and_phrase_top_5)
    metrics["file_and_phrase_match_mean_r_at_10"] = \
        sum(map(lambda n: n / 10, num_matches_on_file_and_phrase_top_10)) / len(num_matches_on_file_and_phrase_top_10)

    #Percent first match metrics give the percentage of queries that had their first relevant match within the top K results.
    #For example, file_match_percent_first_match_in_top_5=.8 means that 80% of the queries had the first relevant match
    #(when considering only the target file), show up within the first 5 results.
    #For example, file_and_phrase_match_percent_first_match_in_top_10=.7 means that 70% of the queries had the first
    #relevant match (when considering both the target file and matching phrase), show up within the first 10 results.
    metrics["file_match_percent_first_match_in_top_1"] = \
        len([x for x in first_matches_on_file if 1<=x<=1]) / len(first_matches_on_file)
    metrics["file_match_percent_first_match_in_top_3"] = \
        len([x for x in first_matches_on_file if 1<=x<=3]) / len(first_matches_on_file)
    metrics["file_match_percent_first_match_in_top_5"] = \
        len([x for x in first_matches_on_file if 1<=x<=5]) / len(first_matches_on_file)
    metrics["file_match_percent_first_match_in_top_10"] = \
        len([x for x in first_matches_on_file if 1<=x<=10]) / len(first_matches_on_file)
    metrics["file_and_phrase_match_percent_first_match_in_top_1"] = \
        len([x for x in first_matches_on_file_and_phrase if 1<=x<=1]) / len(first_matches_on_file_and_phrase)
    metrics["file_and_phrase_match_percent_first_match_in_top_3"] = \
        len([x for x in first_matches_on_file_and_phrase if 1<=x<=3]) / len(first_matches_on_file_and_phrase)
    metrics["file_and_phrase_match_percent_first_match_in_top_5"] = \
        len([x for x in first_matches_on_file_and_phrase if 1<=x<=5]) / len(first_matches_on_file_and_phrase)
    metrics["file_and_phrase_match_percent_first_match_in_top_10"] = \
        len([x for x in first_matches_on_file_and_phrase if 1<=x<=10]) / len(first_matches_on_file_and_phrase)

    #Mean Reciprocal Rank metrics. The reciprocal rank of a query response is the multiplicative inverse of the rank
    #of the first correct answer: 1 for first place, 1⁄2 for second place, 1⁄3 for third place and so on.
    #The mean reciprocal rank is the average of the reciprocal ranks of results for across all test queries.
    metrics["file_match_mean_reciprocal_rank"] = \
        sum(map(lambda n: 1 / n, first_matches_on_file)) / len(first_matches_on_file)
    metrics["file_match_and_phrase_mean_reciprocal_rank"] = \
        sum(map(lambda n: 1 / n, first_matches_on_file_and_phrase)) / len(first_matches_on_file_and_phrase)

    return metrics

def run_queries(customer_id: int, corpus_id: int, query_address: str, jwt_token: str, queries_file: str):
    """This runs all test queries, parses the results, and calculates metrics which are returned.
    Args:
        customer_id: Unique customer ID in vectara platform.
        corpus_id: ID of the corpus to which data needs to be indexed.
        query_address: Address of the querying server. e.g., serving.vectara.io
        jwt_token: A valid Auth token.
        queries_file: Path to the file containing the queries to run in this evaluation.

    Returns:
        (response, True) in case of success and returns (error, False) in case of failure.

    """
    print('Running queries from ' + queries_file)
    queries = _get_queries_list(queries_file)

    if len(queries) == 0:
        return {"no_queries_found_in": queries_file}

    #Initialize arrays of size 'queries.length' to store the metrics for the queries
    #See compute_metrics() for information on the required structure of these variables
    num_matches_on_file_top_1 = [[0] * 1 for i in range(len(queries))]
    num_matches_on_file_top_3 = [[0] * 3 for i in range(len(queries))]
    num_matches_on_file_top_5 = [[0] * 5 for i in range(len(queries))]
    num_matches_on_file_top_10 = [[0] * 10 for i in range(len(queries))]

    num_matches_on_file_and_phrase_top_1 = [0] * len(queries)
    num_matches_on_file_and_phrase_top_3 = [0] * len(queries)
    num_matches_on_file_and_phrase_top_5 = [0] * len(queries)
    num_matches_on_file_and_phrase_top_10 = [0] * len(queries)

    first_matches_on_file = [0] * len(queries)
    first_matches_on_file_and_phrase = [0] * len(queries)

    #Run each query and record the metrics
    for this_query in queries:
        print(this_query)
        #Skip any queries that were not parsed properly
        if 'num' not in this_query:
            continue
        print('Running ' + str(this_query["num"]) + '. ' + this_query["query"])

        #Run query
        response = _run_query(customer_id, corpus_id, query_address, jwt_token, this_query)

        #If the query failed, just ignore it and continue on with the next query
        if response.status_code != 200:
            logging.error("Query %s failed, so not counting its metrics. Failure details: code %d, reason %s, text %s",
                          this_query["num"],
                          response.status_code,
                          response.reason,
                          response.text)
            continue

        #This contains the raw results from running this query
        response_dict = json.loads(response.text)

        #Get array of document IDs with the ID stripped down to just the number prefix for the originating file name
        doc_ids = []
        for doc in response_dict["responseSet"][0]["document"]:
            doc_file_name = os.path.basename(doc["id"])
            doc_ids.append(doc_file_name.split('-')[0])

        #For each item in this query's 'matches' array:
        # get the result number for the first time a matching doc was returned
        # get the result number for the first time both a matching doc and its phrase were returned
        # get the number of results within the top 1 that match on a doc; and top3... and top 5... and top 10
        # get the number of results within the top 1 that match on a doc and its phrase; and top3... and top 5... and top 10
        found_match_on_file = False
        found_match_on_file_and_phrase = False
        for match in this_query["matches"]:
            print("Checking match [" + match["file-num"] + "]: " + match["phrase"])
            response_ct = 0
            for this_response in response_dict["responseSet"][0]["response"]:
                response_ct += 1
                snippet = this_response["text"]
                doc_id = doc_ids[this_response["documentIndex"]]
                #print("  Response " + str(response_ct) + ": [" + str(doc_id) + "]. " + str(snippet))

                if match["file-num"] == doc_id:
                    print("  Found file match for query " + str(this_query["num"]) + " at response spot " + str(response_ct))
                    print("    Response " + str(response_ct) + ": [" + str(doc_id) + "]. " + str(snippet))
                    #Record counts for p@k metrics
                    if response_ct <= 1:
                        num_matches_on_file_top_1[this_query["num"]-1][response_ct-1] = 1
                    if response_ct <= 3:
                        num_matches_on_file_top_3[this_query["num"]-1][response_ct-1] = 1
                    if response_ct <= 5:
                        num_matches_on_file_top_5[this_query["num"]-1][response_ct-1] = 1
                    if response_ct <= 10:
                        num_matches_on_file_top_10[this_query["num"]-1][response_ct-1] = 1
                    #Record count for first match metric if we haven't already found a match for this query
                    if found_match_on_file == False or response_ct < first_matches_on_file[this_query["num"]-1]:
                        first_matches_on_file[this_query["num"]-1] = response_ct
                        found_match_on_file = True

                if match["file-num"] == doc_id and strings_overlap(snippet, match["phrase"]):
                    print("  Found file and phrase match for query " + str(this_query["num"]) + " at response spot " + str(response_ct))
                    print("    Response " + str(response_ct) + ": [" + str(doc_id) + "]. " + str(snippet))
                    #Record counts for p@k metrics
                    num_matches_on_file_and_phrase_top_1[this_query["num"]-1] += (1 if response_ct <= 1 else 0)
                    num_matches_on_file_and_phrase_top_3[this_query["num"]-1] += (1 if response_ct <= 3 else 0)
                    num_matches_on_file_and_phrase_top_5[this_query["num"]-1] += (1 if response_ct <= 5 else 0)
                    num_matches_on_file_and_phrase_top_10[this_query["num"]-1] += (1 if response_ct <= 10 else 0)
                    #Record count for first match metric if we haven't already found a match for this query
                    if found_match_on_file_and_phrase == False or response_ct < first_matches_on_file_and_phrase[this_query["num"]-1]:
                        first_matches_on_file_and_phrase[this_query["num"]-1] = response_ct
                        found_match_on_file_and_phrase = True

        print('\n')

    #Create 'metrics' dict to store aggregated query metrics
    metrics = compute_metrics(num_matches_on_file_top_1, num_matches_on_file_top_3,
                              num_matches_on_file_top_5, num_matches_on_file_top_10,
                              num_matches_on_file_and_phrase_top_1, num_matches_on_file_and_phrase_top_3,
                              num_matches_on_file_and_phrase_top_5, num_matches_on_file_and_phrase_top_10,
                              first_matches_on_file, first_matches_on_file_and_phrase)

    return metrics

if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s", level=logging.INFO)

    parser = argparse.ArgumentParser(description="Vectara evaluation example")

    parser.add_argument("--customer-id", type=int, required=True,
                        help="Unique customer ID in Vectara platform.")
    parser.add_argument("--corpus-id", type=int,
                        help="ID of corpus that contains the indexed data. If this is not provided then "
                             "a new corpus will be created and this bundle's data will be uploaded to it.")
    parser.add_argument("--admin-endpoint", help="The endpoint of admin server.",
                        default="admin.vectara.io")
    parser.add_argument("--indexing-endpoint", help="The endpoint of indexing server.",
                        default="indexing.vectara.io")
    parser.add_argument("--serving-endpoint", help="The endpoint of querying server.",
                        default="serving.vectara.io")
    parser.add_argument("--app-client-id",  required=True,
                        help="This app client should have enough rights.")
    parser.add_argument("--app-client-secret", required=True)
    parser.add_argument("--auth-url",  required=True,
                        help="The cognito auth url for this customer.")
    parser.add_argument("--bundle", help="Which test bundle you want to use for the evaluation.",
                        default="app-search")

    args = parser.parse_args()

    if args:
        token = _get_jwt_token(args.auth_url, args.app_client_id, args.app_client_secret)

        if token:
            # Create a corpus and upload the test data if we were not given a corpus ID
            if args.corpus_id is None:
                result, status, created_corpus_id = create_corpus(args.customer_id,
                                              args.admin_endpoint,
                                              token,
                                              args.bundle)
                logging.info("Created corpus to store the test data response: %s", result.text)
                args.corpus_id = created_corpus_id

                # Upload the data for this evaluation bundle
                result, status = upload_data(args.customer_id,
                                      args.corpus_id,
                                      args.indexing_endpoint,
                                      "bundles/" + args.bundle + "/data",
                                      token)
                logging.info("Data for %s bundle indexed: %s", args.bundle, result)

            print('Using the following corpus ID for the test queries: ' + str(args.corpus_id))

            # Run the queries for this evaluation bundle
            metrics = run_queries(args.customer_id,
                                  args.corpus_id,
                                  args.serving_endpoint,
                                  token,
                                  "bundles/" + args.bundle + "/queries.csv")

            # Save the metrics from the query test to a file
            print("Metrics: " + str(metrics))
            results_filename = "results/results-" + args.bundle + "-" + \
                               datetime.datetime.now().strftime("%m_%d_%Y_%H_%M_%S") + ".json"
            text_file = open(results_filename, "w")
            n = text_file.write(json.dumps(metrics))
            text_file.close()

            logging.info("Evaluation metrics written to " + results_filename)
        else:
            logging.error("Could not generate an auth token. Please check your credentials.")
