import modal
import tweepy
import os

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements(requirements_txt="requirements.txt")
)
stub = modal.Stub("arxivy-twitter-ingest", image=image)

def init_twitter_v2():
    api_key = os.environ["TWITTER_ACCESS_TOKEN"]
    api_secret = os.environ["TWITTER_ACCESS_TOKEN_SECRET"]
    consumer_key = os.environ["TWITTER_API_KEY"]
    consumer_secret = os.environ["TWITTER_API_SECRET"]
    bearer_token = os.environ["TWITTER_BEARER_TOKEN"]
    return tweepy.Client(
        access_token=api_key,
        access_token_secret=api_secret,
        bearer_token=bearer_token,
        consumer_secret=consumer_secret,
        consumer_key=consumer_key)

@stub.function(secret=modal.Secret.from_name("twitter-secret"))
def get_arxivy_tweets():
    client = init_twitter_v2()
    response = client.get_home_timeline(max_results=2, tweet_fields="organic_metrics")
    print(response)
    for data in response.data:
        print(data)



@stub.local_entrypoint()
def main():
    get_arxivy_tweets.call()