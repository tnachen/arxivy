import modal
import tweepy
import os

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements(requirements_txt="requirements.txt")
)
stub = modal.Stub("arxivy-twitter-ingest", image=image)

def init_twitter():
    api_key = os.environ["TWITTER_ACCESS_TOKEN"]
    api_secret = os.environ["TWITTER_ACCESS_TOKEN_SECRET"]
    consumer_key = os.environ["TWITTER_API_KEY"]
    consumer_secret = os.environ["TWITTER_API_SECRET"]
    auth = tweepy.OAuthHandler(consumer_key=consumer_key, consumer_secret=consumer_secret)
    auth.set_access_token(key=api_key, secret=api_secret)
    return tweepy.API(auth)

@stub.function(secret=modal.Secret.from_name("twitter-secret"))
def get_arxivy_tweets():
    api = init_twitter()
    tweets = api.home_timeline(count=20)
    for tweet in tweets:
        print(tweet.text)

@stub.local_entrypoint()
def main():
    get_arxivy_tweets.call()