import type { MetadataRoute } from 'next'
 
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Map360',
    short_name: 'Map360',
    description:
      'A collaborative 3D mapping PWA where groups capture places and build a shared world.',
    start_url: '/',
    display: 'standalone',
    background_color: '#f4f4f5',
    theme_color: '#27272a',
    icons: [
      {
        src: '/icon-192x192.png',
        sizes: '192x192',
        type: 'image/png',
      },
      {
        src: '/icon-512x512.png',
        sizes: '512x512',
        type: 'image/png',
      },
    ],
  }
}