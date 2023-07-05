CREATE TABLE twitter_papers (
    tweet_id integer primary key,
    user text not null,
    paper_link text not null,
    views integer default 0,
)