/** All browser calls go to /backend/*, which Vercel proxies to your FastAPI server.
 *  That keeps the login cookie on one domain, so frontend and backend behave as one app. */
module.exports = {
  async rewrites() {
    const api = process.env.API_URL || "http://localhost:8000";
    return [{ source: "/backend/:path*", destination: `${api}/:path*` }];
  },
};
