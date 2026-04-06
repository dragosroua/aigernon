/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      // Proxy all API routes to the backend
      // Root endpoints (for POST/GET without path segments)
      {
        source: '/auth',
        destination: `${apiUrl}/auth`,
      },
      {
        source: '/chat',
        destination: `${apiUrl}/chat`,
      },
      {
        source: '/sessions',
        destination: `${apiUrl}/sessions`,
      },
      {
        source: '/projects',
        destination: `${apiUrl}/projects`,
      },
      {
        source: '/memory',
        destination: `${apiUrl}/memory`,
      },
      {
        source: '/notifications',
        destination: `${apiUrl}/notifications`,
      },
      {
        source: '/system',
        destination: `${apiUrl}/system`,
      },
      {
        source: '/coaching',
        destination: `${apiUrl}/coaching`,
      },
      // Nested paths
      {
        source: '/auth/:path*',
        destination: `${apiUrl}/auth/:path*`,
      },
      {
        source: '/chat/:path*',
        destination: `${apiUrl}/chat/:path*`,
      },
      {
        source: '/sessions/:path*',
        destination: `${apiUrl}/sessions/:path*`,
      },
      {
        source: '/projects/:path*',
        destination: `${apiUrl}/projects/:path*`,
      },
      {
        source: '/memory/:path*',
        destination: `${apiUrl}/memory/:path*`,
      },
      {
        source: '/notifications/:path*',
        destination: `${apiUrl}/notifications/:path*`,
      },
      {
        source: '/system/:path*',
        destination: `${apiUrl}/system/:path*`,
      },
      {
        source: '/coaching/:path*',
        destination: `${apiUrl}/coaching/:path*`,
      },
    ];
  },
};

export default nextConfig;
