export async function api<T = any>(path: string, opts: { method?: string; body?: any; form?: FormData } = {}): Promise<T> {
  const res = await fetch("/backend" + path, {
    method: opts.method || (opts.body !== undefined || opts.form ? "POST" : "GET"),
    credentials: "include",
    headers: opts.body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: opts.form || (opts.body !== undefined ? JSON.stringify(opts.body) : undefined),
  });
  if (!res.ok) {
    let msg = "Something went wrong. Please try again.";
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : j.detail?.[0]?.msg || msg;
    } catch {}
    const err: any = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return (await res.json()) as T;
}
