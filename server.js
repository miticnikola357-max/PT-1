const express = require("express");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.static(path.join(__dirname, "public")));

let cachedToken = null;
let tokenExpiry = 0;

async function getSpotifyToken() {
  if (cachedToken && Date.now() < tokenExpiry) return cachedToken;

  const res = await fetch(
    "https://open.spotify.com/get_access_token?reason=transport&productType=web_player",
    {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        Accept: "application/json",
      },
    }
  );

  if (!res.ok) throw new Error(`Token request failed: ${res.status}`);

  const data = await res.json();
  cachedToken = data.accessToken;
  tokenExpiry = data.accessTokenExpirationTimestampMs || Date.now() + 300_000;
  return cachedToken;
}

function parseEpisodeId(input) {
  const trimmed = input.trim();
  const patterns = [
    /spotify\.com\/episode\/([a-zA-Z0-9]{22})/,
    /spotify:episode:([a-zA-Z0-9]{22})/,
    /^([a-zA-Z0-9]{22})$/,
  ];
  for (const p of patterns) {
    const m = trimmed.match(p);
    if (m) return m[1];
  }
  return null;
}

async function fetchTranscript(episodeId, token) {
  const url = `https://spclient.wg.spotify.com/transcript-read-along/v2/episode/${episodeId}?format=json`;
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
      Accept: "application/json",
      "App-Platform": "WebPlayer",
    },
  });

  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Transcript fetch failed: ${res.status}`);
  return res.json();
}

async function fetchEpisodeMetadata(episodeId, token) {
  const url = `https://api.spotify.com/v1/episodes/${episodeId}`;
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
  });

  if (!res.ok) return null;
  return res.json();
}

app.get("/api/transcript/:episodeId", async (req, res) => {
  try {
    const episodeId = parseEpisodeId(req.params.episodeId);
    if (!episodeId) {
      return res.status(400).json({ error: "Invalid episode ID or URL" });
    }

    const token = await getSpotifyToken();
    const [transcript, metadata] = await Promise.all([
      fetchTranscript(episodeId, token),
      fetchEpisodeMetadata(episodeId, token),
    ]);

    if (!transcript) {
      return res.status(404).json({
        error: "No transcript available for this episode",
      });
    }

    const sections = (transcript.section || []).map((s) => ({
      startMs: s.startMs,
      text: (s.text || { sentence: [] }).sentence
        .map((w) => w.text)
        .join(" "),
    }));

    const result = {
      episodeId,
      title: metadata?.name || null,
      show: metadata?.show?.name || null,
      image:
        metadata?.images?.[0]?.url || metadata?.show?.images?.[0]?.url || null,
      duration: metadata?.duration_ms || null,
      sections,
    };

    res.json(result);
  } catch (err) {
    console.error("Error fetching transcript:", err.message);
    res.status(500).json({ error: err.message });
  }
});

app.get("/api/parse-url", (req, res) => {
  const url = req.query.url;
  if (!url) return res.status(400).json({ error: "URL required" });
  const id = parseEpisodeId(url);
  if (!id) return res.status(400).json({ error: "Could not parse episode ID" });
  res.json({ episodeId: id });
});

app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
