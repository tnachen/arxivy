CREATE TABLE papers (
    user text not null,
    profile_image text,
    paper_link text not null,
    views integer default 0,
    source text not null,
    created_at timestamp not null
);

create unique index idx_papers_paper_link on papers (paper_link);