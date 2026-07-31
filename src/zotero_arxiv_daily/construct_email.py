from .protocol import Paper, TLDR_FIELDS
import hashlib
import hmac
from html import escape
import math
from urllib.parse import urlencode


framework = """
<!DOCTYPE HTML>
<html>
<head>
  <style>
    .star-wrapper {
      font-size: 1.3em; /* 调整星星大小 */
      line-height: 1; /* 确保垂直对齐 */
      display: inline-flex;
      align-items: center; /* 保持对齐 */
    }
    .half-star {
      display: inline-block;
      width: 0.5em; /* 半颗星的宽度 */
      overflow: hidden;
      white-space: nowrap;
      vertical-align: middle;
    }
    .full-star {
      vertical-align: middle;
    }
  </style>
</head>
<body>

<div>
    __CONTENT__
</div>

<br><br>
<div>
To unsubscribe, remove your email in your Github Action setting.
</div>

</body>
</html>
"""

def get_empty_html():
  block_template = """
  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
  <tr>
    <td style="font-size: 20px; font-weight: bold; color: #333;">
        No Papers Today. Take a Rest!
    </td>
  </tr>
  </table>
  """
  return block_template


def format_tldr_html(tldr: str | None) -> str:
    normalized = (tldr or "").replace("\r\n", "\n").replace("\r", "\n")
    labels = {label for _, label in TLDR_FIELDS}
    rendered = []
    for line in normalized.split("\n"):
        label, separator, value = line.partition("：")
        if separator and label.strip() in labels:
            rendered.append(
                '<div class="summary-section" style="padding: 4px 0;">'
                f"<strong>{escape(label.strip())}：</strong>{escape(value.strip())}"
                "</div>"
            )
        else:
            rendered.append(escape(line))
    return "<br>".join(rendered)


def get_feedback_html(
    title: str,
    paper_url: str | None,
    feedback_endpoint: str | None,
    feedback_secret: str | None,
) -> str:
    if not feedback_endpoint or not feedback_secret:
        return ""
    buttons = [
        ("重要", "important", "#2da44e"),
        ("已读", "read", "#57606a"),
        ("不感兴趣", "not_interested", "#cf222e"),
    ]
    links = []
    for label, value, color in buttons:
        href = build_feedback_url(feedback_endpoint, feedback_secret, paper_url or "", title or "", value)
        links.append(
            f'<a href="{href}" '
            'style="display: inline-block; text-decoration: none; font-size: 13px; '
            f'font-weight: bold; color: #fff; background-color: {color}; '
            'padding: 6px 10px; border-radius: 4px; margin-right: 6px;">'
            f"反馈：{label}</a>"
        )
    return f"""
    <tr>
        <td style="font-size: 13px; color: #333; padding: 8px 0;">
            {''.join(links)}
        </td>
    </tr>
"""


def build_feedback_url(
    endpoint: str,
    secret: str,
    paper_url: str,
    title: str,
    action: str,
) -> str:
    payload = f"{action}\n{paper_url}\n{title}"
    signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    query = urlencode(
        {
            "action": action,
            "paper_url": paper_url,
            "title": title,
            "signature": signature,
        }
    )
    return f"{endpoint.rstrip('/')}?{query}"


def get_block_html(
    title: str,
    authors: str,
    rate: str,
    tldr: str,
    pdf_url: str,
    affiliations: str = None,
    paper_url: str = None,
    source: str = None,
    venue: str = None,
    published_date: str = None,
    feedback_endpoint: str = None,
    feedback_secret: str = None,
):
    source_text = venue or source or "Unknown"
    if source and venue and source.lower() not in venue.lower():
        source_text = f"{source}: {venue}"
    published_date = published_date or "Unknown"
    link_url = pdf_url or paper_url
    link_label = "PDF" if pdf_url else "期刊网页"
    feedback_html = get_feedback_html(title, paper_url or link_url, feedback_endpoint, feedback_secret)
    block_template = """
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
    <tr>
        <td style="font-size: 20px; font-weight: bold; color: #333;">
            {title}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #666; padding: 8px 0;">
            {authors}
            <br>
            <i>{affiliations}</i>
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>Relevance:</strong> {rate}
            <br>
            <strong>Source:</strong> {source_text}
            <br>
            <strong>Date:</strong> {published_date}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>中文速览:</strong> {tldr}
        </td>
    </tr>
    {feedback_html}

    <tr>
        <td style="padding: 8px 0;">
            <a href="{link_url}" style="display: inline-block; text-decoration: none; font-size: 14px; font-weight: bold; color: #fff; background-color: #d9534f; padding: 8px 16px; border-radius: 4px;">{link_label}</a>
        </td>
    </tr>
</table>
"""
    return block_template.format(
        title=title,
        authors=authors,
        rate=rate,
        tldr=format_tldr_html(tldr),
        link_url=link_url,
        link_label=link_label,
        affiliations=affiliations,
        source_text=source_text,
        published_date=published_date,
        feedback_html=feedback_html,
    )

def get_stars(score:float):
    full_star = '<span class="full-star">⭐</span>'
    half_star = '<span class="half-star">⭐</span>'
    low = 6
    high = 8
    if score <= low:
        return ''
    elif score >= high:
        return full_star * 5
    else:
        interval = (high-low) / 10
        star_num = math.ceil((score-low) / interval)
        full_star_num = int(star_num/2)
        half_star_num = star_num - full_star_num * 2
        return '<div class="star-wrapper">'+full_star * full_star_num + half_star * half_star_num + '</div>'


def render_email(
    papers:list[Paper],
    feedback_endpoint: str | None = None,
    feedback_secret: str | None = None,
) -> str:
    parts = []
    if len(papers) == 0 :
        return framework.replace('__CONTENT__', get_empty_html())
    
    for p in papers:
        #rate = get_stars(p.score)
        rate = round(p.score, 1) if p.score is not None else 'Unknown'
        author_list = [a for a in p.authors]
        num_authors = len(author_list)
        if num_authors <= 5:
            authors = ', '.join(author_list)
        else:
            authors = ', '.join(author_list[:3] + ['...'] + author_list[-2:])
        if p.affiliations is not None:
            affiliations = p.affiliations[:5]
            affiliations = ', '.join(affiliations)
            if len(p.affiliations) > 5:
                affiliations += ', ...'
        else:
            affiliations = 'Unknown Affiliation'
        parts.append(
            get_block_html(
                p.title,
                authors,
                rate,
                p.tldr,
                p.pdf_url,
                affiliations,
                paper_url=p.url,
                source=p.source,
                venue=p.venue,
                published_date=p.published_date,
                feedback_endpoint=feedback_endpoint,
                feedback_secret=feedback_secret,
            )
        )

    content = '<br>' + '</br><br>'.join(parts) + '</br>'
    return framework.replace('__CONTENT__', content)
