from datetime import datetime
from html import entities
import logging
from flask import Flask
from flask_restx import Resource, Api
from google.cloud import datastore
from google.cloud import language_v1 as language
import os

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "key.json"

"""
This Flask app shows some examples of the types of requests you could build.
There is currently a GET request that will return all the data in GCP Datastore.
There is also a POST request that will analyse some given text then store the text and its sentiment in GCP Datastore.


The sentiment analysis of the text is being done by Google's NLP API. 
This API can be used to find the Sentiment, Entities, Entity-Sentiment, Syntax, and Content-classification of texts.
Find more about this API here:
https://cloud.google.com/natural-language/docs/basics
For sample code for implementation, look here (click 'Python' above the code samples):
https://cloud.google.com/natural-language/docs/how-to
Note: The analyze_text_sentiment() method below simply copies the 'Sentiment' part of the above documentation.


The database we are using is GCP Datastore (AKA Firestore in Datastore mode). 
This is a simple NoSQL Document database offering by Google:
https://cloud.google.com/datastore
You can access the database through the GCP Cloud Console (find Datastore in the side-menu)


Some ideas of things to build:
- At the moment, the code only stores the analysis of the first sentence of a given text. Modify the POST request to
 also analyse the rest of the sentences. 
- GET Request that returns a single entity based on its ID
- POST Request that will take a list of text items and give it a sentiment then store it in GCP Datastore
- DELETE Request to delete an entity from Datastore based on its ID
- Implement the other analyses that are possible with Google's NLP API


We are using Flask: https://flask.palletsprojects.com/en/2.0.x/
Flask RESTX is an extension of Flask that allows us to document the API with Swagger: https://flask-restx.readthedocs.io/en/latest/
"""

app = Flask(__name__)
api = Api(app)

api = api.namespace('Gavin\'s Great API', description='Just seeing if this works')

parser = api.parser()
parser.add_argument("text", type=str, help="Text", location="form")

parser_id = api.parser()
parser_id.add_argument("ID", type=int, help= "ID", location="args")


@api.route("/api/text")
class Text(Resource):
    @api.expect(parser_id)
    def get(self):
        """
        This GET request will return data based on id
        """
        # Create a Cloud Datastore client.
        datastore_client = datastore.Client()

        args = parser_id.parse_args()
        text = args["ID"]

        # Get the datastore 'kind' which are 'Sentences'
        query = datastore_client.query(kind="Sentences")
        text_entities = list(query.fetch())

        # Gets All
        # result = {}
        # for text_entity in text_entities:
        #     result[str(text_entity.id)] = {
        #         "text": str(text_entity["text"]),
        #         "timestamp": str(text_entity["timestamp"]),
        #         "sentiment": str(text_entity["sentiment"]),
        #         "entities": (text_entity["entities"]),
        #     }
        # return result

        # Parse the data into a dictionary format
        result = {}
        for text_entity in text_entities:
            if(text_entity.id == text):
                result[str(text_entity.id)] = {
                    "text": str(text_entity["text"]),
                    "timestamp": str(text_entity["timestamp"]),
                    "sentiment": str(text_entity["sentiment"]),
                    "entities": (text_entity["entities"]),
                }
                return result       
        return "Id was not found in the database"

    @api.expect(parser_id)
    def delete(self):
        """
        This DELETE request will delete data based on id
        """
        # Create a Cloud Datastore client.
        datastore_client = datastore.Client()

        args = parser_id.parse_args()
        text = args["ID"]

        # Get the datastore 'kind' which are 'Sentences'
        query = datastore_client.query(kind="Sentences")
        text_entities = list(query.fetch())

        # Deletes all
        for text_entity in text_entities:
            datastore_client.delete(text_entity.key)
        return "Delete All Successful" 

        # Deletes one item based on id
        for text_entity in text_entities:
            if(text_entity.id == text):
                datastore_client.delete(text_entity.key)
                return "Delete Successful"   
        return "Id was not found in the database"



    @api.expect(parser)
    def post(self):
        """
        This POST request will accept a 'text', analyze the sentiment analysis of the first sentence, store
        the result to datastore as a 'Sentence', and also return the result.
        """
        datastore_client = datastore.Client()

        args = parser.parse_args()
        text = args["text"]
        
        result = {}
        analyze = analyze_text_sentiment(text)
        for i in range(len(analyze)):
            sentiment = analyze[i].get("sentiment score")
            fragment = analyze[i].get("text")
            entityList = analyze[i].get("entities")

            # Assign a label based on the score
            overall_sentiment = "unknown"
            if sentiment > 0:
                overall_sentiment = "positive"
            if sentiment < 0:
                overall_sentiment = "negative"
            if sentiment == 0:
                overall_sentiment = "neutral"

            current_datetime = datetime.now()

            # The kind for the new entity. This is so all 'Sentences' can be queried.
            kind = "Sentences"

            # Create a key to store into datastore
            key = datastore_client.key(kind)
            # If a key id is not specified then datastore will automatically generate one. For example, if we had:
            # key = datastore_client.key(kind, 'sample_task')
            # instead of the above, then 'sample_task' would be the key id used.

            # Construct the new entity using the key. Set dictionary values for entity
            entity = datastore.Entity(key)
            entity["text"] = fragment
            entity["timestamp"] = current_datetime
            entity["sentiment"] = overall_sentiment
            entity["entities"] = entityList

            # Save the new entity to Datastore.
            datastore_client.put(entity)

            result[str(entity.key.id)] = {
                "text": fragment,
                "timestamp": str(current_datetime),
                "sentiment": overall_sentiment,
                "entities": entityList,
            }
        
        return result


@app.errorhandler(500)
def server_error(e):
    logging.exception("An error occurred during a request.")
    return (
        """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(
            e
        ),
        500,
    )

def analyze_text_sentiment(text):
    """
    This is modified from the Google NLP API documentation found here:
    https://cloud.google.com/natural-language/docs/analyzing-sentiment
    It makes a call to the Google NLP API to retrieve sentiment analysis.
    """
    client = language.LanguageServiceClient()
    document = language.Document(content=text, type_=language.Document.Type.PLAIN_TEXT)

    response = client.analyze_sentiment(document=document)

    # Format the results as a dictionary
    sentiment = response.document_sentiment
    results = dict(
        text=text,
        score=f"{sentiment.score:.1%}",
        magnitude=f"{sentiment.magnitude:.1%}",
    )

    # Print the results for observation
    for k, v in results.items():
        print(f"{k:10}: {v}")

    # Get sentiment for all sentences in the document
    sentence_sentiment = []
    for sentence in response.sentences:
        item = {}

        item["text"] = sentence.text.content
        item["sentiment score"] = sentence.sentiment.score
        item["sentiment magnitude"] = sentence.sentiment.magnitude
        item["entities"] = analyze_entities(sentence.text.content)

        sentence_sentiment.append(item)

    return sentence_sentiment

def analyze_entities(text):
    """
    Analyzing Entities in a String

    Args:
      text_content The text content to analyze
    """
    client = language.LanguageServiceClient()
    document = language.Document(content=text, type_=language.Document.Type.PLAIN_TEXT)

    response = client.analyze_entities(document=document)

    entityList = []
    # Loop through entitites returned from the API
    for entity in response.entities:
        item = {}

        item["name"] = entity.name
        item["type"] = language.Entity.Type(entity.type_).name
        item["salience score"] = entity.salience

        list = {}
        for metadata_name, metadata_value in entity.metadata.items():
            list[metadata_name] = metadata_value
        item["metadata"] = list

        mentionList ={}
        for mention in entity.mentions:
            mentionList["Mention text"]= mention.text.content
            mentionList["Mention type"] = language.EntityMention.Type(mention.type_).name
        item["Mentions"] = mentionList

        entityList.append(item)

    return entityList

def analyze_entity_sentiment(text):
    """
    Analyzing Entity Sentiment in a String

    Args:
      text_content The text content to analyze
    """
    client = language.LanguageServiceClient()
    document = language.Document(content=text, type_=language.Document.Type.PLAIN_TEXT)

    response = client.analyze_entity_sentiment(document=document)

    entity_Sentiment_List = []
    # Loop through entitites returned from the API
    for entity in response.entities:
        item = {}
        sentiment = entity.sentiment

        item["name"] = entity.name
        item["type"] = language.Entity.Type(entity.type_).name
        item["salience score"] = entity.salience
        item["entity sentiment score"] = sentiment.score
        item["entity sentiment magnitude"] = sentiment.magnitude

        list = {}
        for metadata_name, metadata_value in entity.metadata.items():
            list[metadata_name] = metadata_value
        item["metadata"] = list

        mentionList ={}
        for mention in entity.mentions:
            mentionList["Mention text"]= mention.text.content
            mentionList["Mention type"] = language.EntityMention.Type(mention.type_).name
        item["Mentions"] = mentionList
    
    return entity_Sentiment_List

def analyze_syntax(text):
    """
    Analyzing Syntax in a String

    Args:
      text_content The text content to analyze
    """
    client = language.LanguageServiceClient()
    document = language.Document(content=text, type_=language.Document.Type.PLAIN_TEXT)

    response = client.analyze_syntax(document=document)

    analyzeSyntaxList = []
    # Loop through tokens returned from the API
    for token in response.tokens:
        # Get the text content of this token. Usually a word or punctuation.
        text = token.text
        list = {}
        list["Token text"] = text.content
        list["Location of this token in overall document"] = text.begin_offset
        
        # Get the part of speech information for this token.
        # Part of speech is defined in:
        # http://www.lrec-conf.org/proceedings/lrec2012/pdf/274_Paper.pdf
        part_of_speech = token.part_of_speech
        # Get the tag, e.g. NOUN, ADJ for Adjective, et al.
        list["Part of Speech tag"] = language.PartOfSpeech.Tag(part_of_speech.tag).name
        # Get the voice, e.g. ACTIVE or PASSIVE
        list["Voice"] = language.PartOfSpeech.Voice(part_of_speech.voice).name
        # Get the tense, e.g. PAST, FUTURE, PRESENT, et al.
        list["Tense"] = language.PartOfSpeech.Tense(part_of_speech.tense).name
        # See API reference for additional Part of Speech information available
        # Get the lemma of the token. Wikipedia lemma description
        # https://en.wikipedia.org/wiki/Lemma_(morphology)
        list["Lemma"] = token.lemma
        # Get the dependency tree parse information for this token.
        # For more information on dependency labels:
        # http://www.aclweb.org/anthology/P13-2017
        dependency_edge = token.dependency_edge
        list["Head token index"] = dependency_edge.head_token_index
        list["Label"] = language.DependencyEdge.Label(dependency_edge.label).name
        analyzeSyntaxList.append(list)
    return analyzeSyntaxList

def classify_text(text):
    """
    Classifying Content in a String

    Args:
      text_content The text content to analyze. Must include at least 20 words.
    """

    client = language.LanguageServiceClient()
    document = language.Document(content=text, type_=language.Document.Type.PLAIN_TEXT)

    response = client.classify_text(document=document)

    categoryList = []
    # Loop through classified categories returned from the API
    for category in response.categories:
        items = {}
        # Get the name of the category representing the document.
        # See the predefined taxonomy of categories:
        # https://cloud.google.com/natural-language/docs/categories
        items["Category name"] = category.name
        # Get the confidence. Number representing how certain the classifier
        # is that this category represents the provided text.
        items["Confidence"] = category.confidence
        
    return categoryList


if __name__ == "__main__":
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    app.run(host="127.0.0.1", port=8080, debug=True)
