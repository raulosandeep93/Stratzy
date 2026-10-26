import requests, re

scripts = [
    'https://d5tgld9he2um8.cloudfront.net/_next/static/chunks/fd9d1056-f324c66ca2b345c0.js',
    'https://d5tgld9he2um8.cloudfront.net/_next/static/chunks/2117-275bfb0091148a78.js',
    'https://d5tgld9he2um8.cloudfront.net/_next/static/chunks/main-app-04a7f9925aa07761.js',
    'https://d5tgld9he2um8.cloudfront.net/_next/static/chunks/c15bf2b0-4669017430090ac3.js',
    'https://d5tgld9he2um8.cloudfront.net/_next/static/chunks/8131-fddf5215c4925b1b.js',
    'https://d5tgld9he2um8.cloudfront.net/_next/static/chunks/7060-2a9ccc31374ab50e.js',
    'https://d5tgld9he2um8.cloudfront.net/_next/static/chunks/4065-2da98f5c5f6a273d.js',
    'https://d5tgld9he2um8.cloudfront.net/_next/static/chunks/3145-36edb27a1c06b85a.js',
    'https://d5tgld9he2um8.cloudfront.net/_next/static/chunks/7648-87e2ecfe1d9cb593.js',
    'https://d5tgld9he2um8.cloudfront.net/_next/static/chunks/2252-cefde362e4ee3e3b.js'
]

endpoints = set()
for url in scripts:
    try:
        t = requests.get(url, timeout=10).text
        for m in re.findall(r'[\"\'`]/api/([a-zA-Z0-9_\-/]+)[\"\'`]', t):
            if any(k in m.lower() for k in ['algo', 'user', 'portfolio', 'invest', 'broker', 'active', 'subscribe', 'order', 'position', 'basket']):
                endpoints.add('/api/' + m)
    except Exception as e:
        pass

for ep in sorted(endpoints):
    print(ep)
