"""Volunteer labelling page (Traditional Chinese). Standalone public app:

    streamlit run app.py

Raters sign in with Google (st.login, email must be verified), get 25 comments at a time and can keep going.
The comments they see are the ones with the fewest ratings so far. See README for setup.
"""
import html
import os
import random
import re

import streamlit as st

st.set_page_config(page_title="PTT 留言標註", page_icon=":material/rate_review:", layout="centered")

import labeler_core as rating  # noqa: E402


@st.cache_resource
def _init():
    rating.init_db()
    return True


_init()

OPTIONS = {"positive": "😊 正面 Positive", "negative": "😠 負面 Negative", "neutral": "😐 中立 Neutral",
           "sarcastic": "🙃 反諷 Sarcastic", "unsure": "🤷 不確定 Not sure"}

CSS = """
<style>
.block-container { max-width: 760px; }
.wv-hero { padding: 1.4rem 1.4rem 1.2rem; border-radius: 18px; margin-bottom: 1rem;
           background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); color: #fff; }
.wv-hero h1 { margin: 0 0 .35rem; font-size: 1.9rem; color: #fff; padding: 0; }
.wv-hero p { margin: 0; font-size: 1.02rem; opacity: .93; line-height: 1.6; }
.wv-steps { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .9rem; }
.wv-steps span { background: rgba(255,255,255,.18); border-radius: 999px; padding: .3rem .85rem; font-size: .92rem; }
.wv-part { display: flex; align-items: center; gap: .8rem; margin: 1.9rem 0 .8rem; }
.wv-part .wv-num { width: 2.4rem; height: 2.4rem; border-radius: 50%; display: flex; align-items: center;
                   justify-content: center; font-weight: 700; color: #fff; background: #4F46E5; flex: none; }
.wv-part b { font-size: 1.2rem; display: block; }
.wv-part small { opacity: .65; }
.wv-meta { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; font-size: .85rem; opacity: .85; margin-bottom: .55rem; }
.wv-no { font-weight: 700; opacity: .6; }
.wv-chip { border-radius: 6px; padding: .05rem .5rem; font-weight: 700; color: #fff; background: #64748B; }
.wv-chip.up { background: #059669; } .wv-chip.down { background: #DC2626; }
.wv-title { opacity: .75; }
.wv-text { font-size: 1.3rem; line-height: 1.6; font-weight: 600; margin: .1rem 0 .7rem; word-break: break-word; }
.wv-done { color: #059669; font-weight: 700; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; }
div[data-testid="stButtonGroup"] button { font-size: 1rem; padding: .45rem .9rem; }
</style>
"""


def tag_chip(tag: str) -> str:
    cls = {"推": "up", "噓": "down"}.get((tag or "")[:1], "")
    return f'<span class="wv-chip {cls}">{html.escape(tag)}</span>' if tag else ""
CATEGORY_ZH = {"general": "綜合", "career": "職場", "finance": "財經", "tech": "科技", "lifestyle": "生活",
               "entertainment": "娛樂", "auto": "汽車", "property": "房產", "social": "社會"}


def plain(text: str) -> str:
    """Show PTT text literally: Streamlit would otherwise read *, _, # or [ ] as Markdown."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|~<>$])", r"\\\1", text or "")


def sign_in() -> str | None:
    dev = os.getenv("LABELER_DEV_EMAIL")  # local testing only; never set this on the deployed app
    if dev:
        return dev.lower()
    if os.getenv("LABELER_OPEN_SIGNIN"):  # temporary: raters type their email, nothing is verified. Use Google login for real raters
        if st.session_state.get("open_email"):
            return st.session_state["open_email"]
        st.title("PTT 留言標註")
        st.write("請輸入你的 Email 開始。我們只用它來避免重複作答，不會公開。")
        st.caption("Enter your email to start. We only use it to avoid duplicate answers; it is never shown publicly.")
        with st.form("open_signin"):
            typed = st.text_input("Email").strip().lower()
            if st.form_submit_button("開始 Start", type="primary") and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", typed):
                st.session_state["open_email"] = typed
                st.rerun()
        return None
    if not st.user.get("is_logged_in", False):
        st.title("PTT 留言標註")
        st.write("請幫忙看看網友在 PTT 留言時的心情是開心、生氣，還是在酸人。每次 25 則，約 3–5 分鐘，可以隨時停下來，也可以繼續做下一組。")
        st.caption("Read some comments from Taiwan's PTT forum and tell us how the writer feels. 25 comments at a time, about 3–5 minutes, stop whenever you like.")
        st.button("用 Google 帳號登入 Sign in with Google", on_click=st.login, type="primary", icon=":material/login:")
        st.caption("我們只用你的 Google Email 來避免重複作答和確認品質，不會公開。留言內容皆為 PTT 上的公開文字。")
        return None
    if not st.user.get("email_verified", False) or not st.user.get("email"):
        st.error("這個 Google 帳號的 Email 尚未驗證，無法使用。 This Google account's email is not verified.")
        st.button("登出 Log out", on_click=st.logout)
        return None
    return str(st.user.email).lower()


SECTION_SIZE = 5


def instructions():
    with st.expander("要怎麼做？ What do I do?", expanded="seen" not in st.session_state):
        st.markdown(
            "**你要做的事很簡單：**讀一則網友的留言，然後選出「寫這則留言的人，心情是哪一種」。\n\n"
            "沒有標準答案，也不是考試，憑你的直覺就好。\n\n"
            "**五個選項：**\n"
            "- **正面**：開心、稱讚、支持。例：「這家真的好吃，下次還要來！」\n"
            "- **負面**：不滿、生氣、批評。例：「服務態度超差，不會再去了。」\n"
            "- **中立**：只是在說明事情、問問題，沒有明顯情緒。例：「請問這間幾點開門？」\n"
            "- **反諷**：字面上像在稱讚，其實是在酸人、挖苦。例：「哇，又延誤兩小時，真是準時的好公司呢。」\n"
            "- **不確定**：看不懂、猜不出來時就選這個，不用硬猜。\n\n"
            "留言上方的小字是它回應的文章標題，和網友按的「推」（讚）或「噓」（倒讚）。這只是提示，不一定代表留言的語氣。\n\n"
            "全部選完後按最下面的「送出」。想再做的話會自動出現下一組，想休息就直接關掉頁面，已送出的不會不見。")
        st.markdown(
            "**What to do:** read each comment and pick the feeling of the person who wrote it. "
            "There is no right answer and it is not a test, just go with your gut. "
            "Positive = happy or praising, Negative = unhappy or criticising, Neutral = just stating or asking, "
            "Sarcastic = sounds nice but is really mocking, Not sure = can't tell. "
            "Press Submit at the bottom when every comment has an answer.")
        st.session_state["seen"] = True


email = sign_in()
if not email:
    st.stop()

stats = rating.rater_stats(email)
with st.sidebar:
    st.caption(email)
    st.metric("已完成 Labelled", stats["labelled"])
    if not os.getenv("LABELER_DEV_EMAIL") and not os.getenv("LABELER_OPEN_SIGNIN"):
        st.button("登出 Log out", on_click=st.logout)

st.markdown(CSS, unsafe_allow_html=True)
st.markdown(
    '<div class="wv-hero"><h1>PTT 留言標註</h1>'
    "<p>看看網友的留言，告訴我們寫的人心情如何。沒有標準答案，憑直覺就好。</p>"
    '<div class="wv-steps"><span>① 讀留言</span><span>② 選心情</span><span>③ 按送出</span></div></div>',
    unsafe_allow_html=True)
instructions()

cats = rating.categories()
choice = st.selectbox("想看哪一類的留言？ Topic", ["all"] + sorted(cats),
                      format_func=lambda c: "全部 All" if c == "all" else f"{CATEGORY_ZH.get(c, c)} ({c}) · {cats[c]}")

if st.session_state.get("batch_cat") != choice or "batch" not in st.session_state:
    st.session_state["batch"] = rating.next_batch(email, None if choice == "all" else choice, rng=random.Random())
    st.session_state["batch_cat"] = choice

if "flash" in st.session_state:
    st.success(f"謝謝你！已儲存 {st.session_state.pop('flash')} 則。想再做一輪的話，直接繼續往下。", icon=":material/check_circle:")

batch = st.session_state["batch"]
if not [b for b in batch if b["kind"] == "item"]:
    st.info("這一類的留言你都標完了，謝謝！可以換一個類別，或晚點再來。 You've labelled everything here.")
    st.stop()

progress = st.empty()
answers = {}
parts = -(-len(batch) // SECTION_SIZE)
for n, it in enumerate(batch, 1):
    if (n - 1) % SECTION_SIZE == 0:
        part = (n - 1) // SECTION_SIZE + 1
        last = min(n + SECTION_SIZE - 1, len(batch))
        st.markdown(f'<div class="wv-part"><span class="wv-num">{part}</span><div><b>第 {part} 組</b>'
                    f"<small>Part {part} of {parts} · 第 {n}–{last} 則</small></div></div>", unsafe_allow_html=True)
    with st.container(border=True):
        done = st.session_state.get(f"r_{it['id']}") is not None
        st.markdown(
            f'<div class="wv-meta"><span class="wv-no">{n}/{len(batch)}</span>{tag_chip(it["tag"])}'
            f'<span class="wv-title">{html.escape(it["post_title"] or "")}</span>'
            f'{"<span class=wv-done>✓</span>" if done else ""}</div>'
            f'<div class="wv-text">{html.escape(it["text"] or "").replace(chr(10), "<br>")}</div>',
            unsafe_allow_html=True)
        answers[it["id"]] = st.pills("這則留言的語氣", list(OPTIONS), selection_mode="single", format_func=OPTIONS.get,
                                     key=f"r_{it['id']}", label_visibility="collapsed")

answered = sum(v is not None for v in answers.values())
progress.progress(answered / len(batch), text=f"已完成 {answered} / {len(batch)} · Done")
st.write("")
if answered < len(batch):
    st.caption(f"還有 {len(batch) - answered} 則沒選。看不懂的請選「🤷 不確定」。 "
               f"{len(batch) - answered} left; pick 'Not sure' if unclear.")
if st.button("送出 Submit", type="primary", icon=":material/send:", disabled=answered < len(batch), width="stretch"):
    saved = rating.save_ratings(email, answers)
    st.session_state.pop("batch")
    st.session_state["flash"] = saved
    st.rerun()
