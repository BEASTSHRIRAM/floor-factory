/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // three / fiber / drei ship ESM that Next handles best when transpiled.
  transpilePackages: ["three", "@react-three/fiber", "@react-three/drei"],
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
