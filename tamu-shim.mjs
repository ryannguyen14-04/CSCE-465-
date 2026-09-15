// tamu-shim.mjs — tiny local proxy that fixes OpenClaw <-> TAMUS AI API compatibility.
// It rewrites assistant messages with `content: null` to `content: ""` (the TAMUS
// proxy's OpenAI layer rejects null, which OpenClaw sends per the OpenAI spec),
// then forwards to the real endpoint. Point OpenClaw's provider baseUrl at
// http://127.0.0.1:8899/openai and put your real key in TAMU_API_KEY here.
import http from "node:http";
import https from "node:https";

const PORT = 8899;
const UPSTREAM = "https://chat-api.tamu.ai";
const KEY = process.env.TAMU_API_KEY;
if (!KEY) { console.error("set TAMU_API_KEY"); process.exit(1); }

http.createServer((req, res) => {
  const chunks = [];
  req.on("data", c => chunks.push(c));
  req.on("end", () => {
    let body = Buffer.concat(chunks);
    // fix content:null on any message
    try {
      const j = JSON.parse(body.toString("utf8"));
      if (Array.isArray(j.messages)) {
        for (const m of j.messages) if (m && m.content === null) m.content = "";
        body = Buffer.from(JSON.stringify(j));
      }
    } catch { /* not JSON (e.g. GET) — pass through */ }

    const u = new URL(req.url, UPSTREAM);
    const upstreamReq = https.request(UPSTREAM + req.url, {
      method: req.method,
      headers: {
        ...req.headers,
        host: new URL(UPSTREAM).host,
        authorization: "Bearer " + KEY,
        "content-length": Buffer.byteLength(body),
        "user-agent": "curl/8.5.0",
      },
    }, up => {
      res.writeHead(up.statusCode, up.headers);
      up.pipe(res);                     // streams SSE through unchanged
    });
    upstreamReq.on("error", e => { res.writeHead(502); res.end(String(e)); });
    upstreamReq.end(body);
  });
}).listen(PORT, "127.0.0.1", () => console.log(`tamu-shim on http://127.0.0.1:${PORT} -> ${UPSTREAM}`));
