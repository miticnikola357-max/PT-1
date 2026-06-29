import type { Context, Config } from "@netlify/functions";

let cachedToken: string | null = null;
let tokenExpiry = 0;

async function getSpotifyToken(): Promise<string> {
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
  return cachedToken!;
}

async function fetchTranscript(episodeId: string, token: string) {
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

async function fetchEpisodeMetadata(episodeId: string, token: string) {
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

export default async (req: Request, context: Context) => {
  const url = new URL(req.url);
  const episodeId = url.pathname.split("/").pop();

  if (!episodeId || !/^[a-zA-Z0-9]{22}$/.test(episodeId)) {
    return new Response(JSON.stringify({ error: "Invalid episode ID" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    const token = await getSpotifyToken();
    const [transcript, metadata] = await Promise.all([
      fetchTranscript(episodeId, token),
      fetchEpisodeMetadata(episodeId, token),
    ]);

    if (!transcript) {
      return new Response(
        JSON.stringify({ error: "No transcript available for this episode" }),
        { status: 404, headers: { "Content-Type": "application/json" } }
      );
    }

    const sections = (transcript.section || []).map((s: any) => ({
      startMs: s.startMs,
      text: (s.text || { sentence: [] }).sentence
        .map((w: any) => w.text)
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

    return new Response(JSON.stringify(result), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err: any) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
};

export const config: Config = {
  path: "/api/transcript/*",
};
