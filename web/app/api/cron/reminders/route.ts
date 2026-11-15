// Vercel Cron calls this daily; it asks the backend to email due weak-topic reminders.
export const dynamic = "force-dynamic";
export const maxDuration = 60;

export async function GET(req: Request) {
  const secret = process.env.CRON_SECRET;
  if (!secret || req.headers.get("authorization") !== `Bearer ${secret}`) {
    return new Response("Unauthorized", { status: 401 });
  }
  const res = await fetch(`${process.env.API_URL}/cron/send-reminders`, {
    method: "POST",
    headers: { Authorization: `Bearer ${secret}` },
  });
  return new Response(await res.text(), { status: res.status });
}
