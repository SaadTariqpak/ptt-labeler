# ptt-labeler

Small Streamlit page where volunteers read PTT comments (Traditional Chinese) and pick the writer's mood.
Answers are stored in a shared Postgres database and analysed elsewhere.

This repo has no secrets. Everything private is set in the Streamlit app's **Secrets** box:

```toml
DATABASE_URL = "postgresql://user:password@host:5432/postgres"
LABELER_OPEN_SIGNIN = "1"      # trial mode: raters type their email (not verified)
```

For verified Google login, remove `LABELER_OPEN_SIGNIN` and add an `[auth]` block (see Streamlit docs for `st.login`).
Never set `LABELER_DEV_EMAIL` on a deployed app: it signs everybody in as one person.

Run locally: `streamlit run app.py` with `DATABASE_URL` and `LABELER_DEV_EMAIL` set.
Deploy: share.streamlit.io, main file `app.py`.
