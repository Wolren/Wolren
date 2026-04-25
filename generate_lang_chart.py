#!/usr/bin/env python3
"""
Generate a GIS-styled language contribution donut chart.
Fetches language bytes from all accessible GitHub repos (owned + contributed to),
excludes specified repos/languages, and saves assets/language-map-pie.png.
"""

import os
import json
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
import numpy as np

# ── Config ────────────────────────────────────────────────────────────────────
TOKEN    = os.environ['GH_TOKEN']
USERNAME = os.environ.get('GH_USERNAME', 'Wolren')
OUT_PATH = os.environ.get('OUT_PATH', 'assets/language-map-pie.png')

# Repos whose language bytes are entirely skipped (SDK/boilerplate noise)
EXCLUDE_REPOS = set(filter(None, os.environ.get('EXCLUDE_REPOS', '').split(',')))

# Individual languages to skip (e.g. auto-generated XML)
EXCLUDE_LANGS = set(filter(None, os.environ.get('EXCLUDE_LANGS', 'C#,C++,HLSL,GLSL,ShaderLab').split(',')))

# Slices smaller than this % are merged into "Other"
MIN_SLICE_PCT = float(os.environ.get('MIN_SLICE_PCT', '1.5'))

HEADERS = {
    'Authorization': f'Bearer {TOKEN}',
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
}

# ── GIS cartographic palette ───────────────────────────────────────────────
GIS_COLORS = [
    '#4A7C59',  # deep forest green   – Python
    '#2E86AB',  # water blue           – TypeScript
    '#C4A35A',  # sandy loam           – SQL
    '#7B4F2E',  # terracotta           – WGSL
    '#6B8F71',  # pale sage            – Kotlin
    '#3D5A80',  # deep ocean           – Java
    '#A8C5A0',  # light meadow         – HTML
    '#D4845A',  # warm clay            – PHP
    '#8B7355',  # parchment brown      – LaTeX
    '#5C7A6B',  # tidal green          – R
    '#9DB4C0',  # overcast sky         – Other
    '#B5C4B1',  # pale lichen          – extra
    '#4E6E58',  # dark canopy          – extra
    '#7A9E9F',  # pale teal            – extra
]

BG_COLOR     = '#0D1117'   # GitHub dark background
PANEL_COLOR  = '#161B22'   # card background
TEXT_COLOR   = '#C9D1D9'   # primary text
SUBTEXT      = '#8B949E'   # secondary text
ACCENT       = '#4A7C59'   # green accent

# ── Fetch repos ───────────────────────────────────────────────────────────────
def get_repos():
    repos, page = [], 1
    while True:
        r = requests.get(
            'https://api.github.com/user/repos',
            headers=HEADERS,
            params={'per_page': 100, 'page': page, 'affiliation': 'owner,collaborator,organization_member'},
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def get_languages(owner, repo):
    r = requests.get(
        f'https://api.github.com/repos/{owner}/{repo}/languages',
        headers=HEADERS,
    )
    if r.status_code == 403 or r.status_code == 404:
        return {}
    r.raise_for_status()
    return r.json()


# ── Aggregate ─────────────────────────────────────────────────────────────────
def collect_language_bytes():
    repos = get_repos()
    totals = {}
    for repo in repos:
        full_name = repo['full_name']
        name      = repo['name']
        if name in EXCLUDE_REPOS or full_name in EXCLUDE_REPOS:
            print(f'  skip repo: {full_name}')
            continue
        langs = get_languages(repo['owner']['login'], name)
        for lang, bytes_ in langs.items():
            if lang in EXCLUDE_LANGS:
                continue
            totals[lang] = totals.get(lang, 0) + bytes_
    return totals


# ── Build chart data ──────────────────────────────────────────────────────────
def build_slices(totals):
    total_bytes = sum(totals.values()) or 1
    pct = {k: v / total_bytes * 100 for k, v in totals.items()}
    # Sort descending
    sorted_langs = sorted(pct.items(), key=lambda x: x[1], reverse=True)
    main, other_pct = [], 0.0
    for lang, p in sorted_langs:
        if p >= MIN_SLICE_PCT:
            main.append((lang, p))
        else:
            other_pct += p
    if other_pct > 0:
        main.append(('Other', other_pct))
    return main


# ── Draw ──────────────────────────────────────────────────────────────────────
def draw_chart(slices):
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

    labels = [s[0] for s in slices]
    sizes  = [s[1] for s in slices]
    colors = (GIS_COLORS * 4)[:len(slices)]

    fig = plt.figure(figsize=(6, 5), facecolor=BG_COLOR)
    ax  = fig.add_axes([0.05, 0.08, 0.90, 0.82])
    ax.set_facecolor(BG_COLOR)

    # --- draw graticule rings (GIS map feel) ---
    for r in np.linspace(0.35, 0.90, 5):
        circle = plt.Circle((0, 0), r, color='#1F2937', fill=False, linewidth=0.4, linestyle='--')
        ax.add_patch(circle)

    # --- donut ---
    wedges, _ = ax.pie(
        sizes,
        colors=colors,
        startangle=90,
        counterclock=False,
        wedgeprops=dict(width=0.45, edgecolor=BG_COLOR, linewidth=1.5),
        radius=1.0,
    )

    # subtle white highlight on each wedge
    for w in wedges:
        w.set_linewidth(1.2)
        w.set_edgecolor('#1F2937')

    # --- centre badge ---
    centre_circle = plt.Circle((0, 0), 0.55, color=PANEL_COLOR, zorder=10)
    ax.add_patch(centre_circle)
    # thin accent ring
    ring = plt.Circle((0, 0), 0.555, color=ACCENT, fill=False, linewidth=1.5, zorder=11)
    ax.add_patch(ring)

    ax.text(0,  0.13, USERNAME, ha='center', va='center',
            fontsize=9, color=ACCENT, fontweight='bold',
            fontfamily='monospace', zorder=12)
    ax.text(0, -0.03, 'LANG', ha='center', va='center',
            fontsize=7, color=SUBTEXT, fontfamily='monospace', zorder=12)
    ax.text(0, -0.18, 'MAP', ha='center', va='center',
            fontsize=14, color=TEXT_COLOR, fontweight='bold',
            fontfamily='monospace', zorder=12)

    # --- legend ---
    legend_patches = [
        mpatches.Patch(
            color=colors[i],
            label=f'{labels[i]}  {sizes[i]:.1f}%'
        )
        for i in range(len(labels))
    ]
    leg = ax.legend(
        handles=legend_patches,
        loc='lower center',
        bbox_to_anchor=(0.5, -0.22),
        ncol=3,
        frameon=True,
        facecolor=PANEL_COLOR,
        edgecolor='#30363D',
        labelcolor=TEXT_COLOR,
        fontsize=6.5,
        handlelength=1.0,
        handleheight=0.9,
        columnspacing=1.0,
    )

    # --- title ---
    ax.set_title(
        'Language Contribution Map',
        color=TEXT_COLOR,
        fontsize=9,
        fontfamily='monospace',
        pad=10,
        loc='center',
    )

    # cardinal compass tick marks (GIS flavour)
    for angle, label in [(90, 'N'), (0, 'E'), (270, 'S'), (180, 'W')]:
        rad = np.radians(angle)
        ax.text(
            1.12 * np.cos(rad), 1.12 * np.sin(rad), label,
            ha='center', va='center',
            fontsize=5.5, color='#30363D', fontfamily='monospace',
        )

    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-1.3, 1.3)
    ax.set_aspect('equal')
    ax.axis('off')

    plt.savefig(
        OUT_PATH,
        dpi=180,
        bbox_inches='tight',
        facecolor=BG_COLOR,
        pad_inches=0.15,
    )
    print(f'Saved chart to {OUT_PATH}')
    plt.close()


# ── JSON dump ─────────────────────────────────────────────────────────────────
def save_json(slices):
    json_path = OUT_PATH.replace('.png', '.json')
    with open(json_path, 'w') as f:
        json.dump({lang: round(pct, 3) for lang, pct in slices}, f, indent=2)
    print(f'Saved breakdown to {json_path}')


# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('Fetching repository language data...')
    totals = collect_language_bytes()
    print(f'Raw totals: {totals}')
    slices = build_slices(totals)
    print(f'Chart slices: {slices}')
    draw_chart(slices)
    save_json(slices)
