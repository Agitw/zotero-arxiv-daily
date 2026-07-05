export default {
  async fetch(request, env) {
    if (request.method !== "GET") {
      return new Response("Method not allowed", { status: 405 });
    }

    const url = new URL(request.url);
    const action = url.searchParams.get("action") || "";
    const paperUrl = url.searchParams.get("paper_url") || "";
    const title = url.searchParams.get("title") || "";
    const signature = url.searchParams.get("signature") || "";
    const allowedActions = new Set(["important", "read", "not_interested"]);
    if (!allowedActions.has(action) || !paperUrl || !signature) {
      return new Response("Bad feedback request", { status: 400 });
    }

    const expected = await hmacHex(env.FEEDBACK_SECRET, `${action}\n${paperUrl}\n${title}`);
    if (!timingSafeEqual(signature, expected)) {
      return new Response("Invalid signature", { status: 403 });
    }

    const body = JSON.stringify(
      {
        paper_feedback: {
          [paperUrl]: action,
        },
      },
      null,
      2,
    );
    const issueTitle = `[paper-feedback] ${action}: ${title || paperUrl}`;
    const response = await fetch(`https://api.github.com/repos/${env.GITHUB_REPOSITORY}/issues`, {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        "Content-Type": "application/json",
        "User-Agent": "zotero-arxiv-daily-feedback-worker",
      },
      body: JSON.stringify({
        title: issueTitle,
        body,
        labels: ["paper-feedback"],
      }),
    });

    if (!response.ok) {
      const message = await response.text();
      return new Response(`GitHub write failed: ${message}`, { status: 502 });
    }

    return new Response(
      `反馈已记录：${action}\n\n你可以关闭这个页面。`,
      {
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
        },
      },
    );
  },
};

async function hmacHex(secret, payload) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret || ""),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const digest = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function timingSafeEqual(left, right) {
  if (left.length !== right.length) {
    return false;
  }
  let diff = 0;
  for (let index = 0; index < left.length; index += 1) {
    diff |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return diff === 0;
}
