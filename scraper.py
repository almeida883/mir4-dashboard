"""
MIR4 NFT Scraper — GitHub Actions
Recolhe lista de NFTs + detalhes (inven, skills, stats) e guarda em JSON
"""
import requests, json, time, os
from datetime import datetime, timezone

BASE = "https://webapi.mir4global.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    "Referer": "https://www.xdraco.com/"
}
CLASS_MAP = {1:"Warrior",2:"Sorcerer",3:"Taoist",4:"Arbalist",5:"Lancer",6:"Darkist"}

def get(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            return r.json()
        except:
            time.sleep(2)
    return {}

def fetch_list(list_type="recent", pages=5):
    results = []
    for page in range(1, pages+1):
        url = f"{BASE}/nft/lists?listType={list_type}&page={page}&class=0&levMin=0&levMax=0&powerMin=0&powerMax=0&priceMin=0&priceMax=0&languageCode=pt"
        data = get(url)
        items = data.get("data", {}).get("lists", [])
        if not items:
            break
        results.extend(items)
        print(f"  [{list_type}] p{page}: {len(items)} NFTs")
        time.sleep(0.3)
    return results

def fetch_detail(transport_id, class_id):
    inven = get(f"{BASE}/nft/character/inven?transportID={transport_id}&languageCode=pt")
    skills = get(f"{BASE}/nft/character/skills?transportID={transport_id}&class={class_id}&languageCode=pt")
    stats = get(f"{BASE}/nft/character/stats?transportID={transport_id}&languageCode=pt")

    # Processar itens lendários/épicos
    items = inven.get("data", [])
    legendary = [i["itemName"] for i in items if str(i.get("grade","")) in ["4","5"]]
    epic = [i["itemName"] for i in items if str(i.get("grade","")) == "3"]

    # Skills com nível > 0
    skill_list = skills.get("data", [])
    trained_skills = {s["skillName"]: int(s["skillLevel"]) for s in skill_list if int(s.get("skillLevel",0)) > 0}

    # Stats principais
    mainstats = {}
    for s in stats.get("data", {}).get("mainstats", []):
        val = s["statValue"].replace(",","")
        try:
            mainstats[s["statName"]] = float(val)
        except:
            mainstats[s["statName"]] = s["statValue"]

    return {
        "legendary_items": legendary,
        "epic_items": epic,
        "legendary_count": len(legendary),
        "epic_count": len(epic),
        "trained_skills": trained_skills,
        "mainstats": mainstats
    }

def process_nft(item):
    info = item.get("info", {})
    trade_dt = info.get("tradeDT", 0)
    transport_id = info.get("transportID")
    class_id = info.get("class", 0)

    record = {
        "nft_id":       info.get("nftID"),
        "seq":          info.get("seq"),
        "transport_id": transport_id,
        "nome":         info.get("characterName",""),
        "classe_id":    class_id,
        "classe":       CLASS_MAP.get(class_id, "?"),
        "nivel":        info.get("lv"),
        "power_score":  info.get("powerScore"),
        "preco_draco":  info.get("price"),
        "mirage_score": info.get("MirageScore",0),
        "mira_x":       info.get("MiraX",0),
        "servidor":     info.get("worldName"),
        "trade_dt":     trade_dt,
        "data_venda":   datetime.fromtimestamp(trade_dt, tz=timezone.utc).strftime("%Y-%m-%d %H:%M") if trade_dt else ""
    }

    # Detalhes completos
    if transport_id:
        detail = fetch_detail(transport_id, class_id)
        record.update(detail)
        time.sleep(0.2)

    return record

def compute_stats(records):
    from collections import defaultdict
    import statistics as st

    stats = {"updated_at": datetime.now(timezone.utc).isoformat(), "total": len(records)}

    # Por classe
    por_classe = defaultdict(list)
    for r in records:
        if r.get("preco_draco") and r.get("classe") != "?":
            por_classe[r["classe"]].append(r["preco_draco"])

    stats["por_classe"] = {
        c: {
            "media": round(st.mean(p)),
            "mediana": round(st.median(p)),
            "min": min(p),
            "max": max(p),
            "count": len(p)
        } for c, p in por_classe.items()
    }

    # Por nível (bucket 10)
    por_nivel = defaultdict(list)
    for r in records:
        if r.get("nivel") and r.get("preco_draco"):
            b = (r["nivel"] // 10) * 10
            por_nivel[b].append(r["preco_draco"])

    stats["por_nivel"] = {
        str(b): {"media": round(st.mean(p)), "mediana": round(st.median(p)), "count": len(p)}
        for b, p in sorted(por_nivel.items())
    }

    # Por PS bucket
    por_ps = defaultdict(list)
    for r in records:
        if r.get("power_score") and r.get("preco_draco"):
            b = (r["power_score"] // 100000) * 100000
            por_ps[b].append(r["preco_draco"])

    stats["por_ps"] = {
        str(b): {"media": round(st.mean(p)), "mediana": round(st.median(p)), "count": len(p)}
        for b, p in sorted(por_ps.items())
    }

    # Items lendários mais comuns nos NFTs caros
    top_records = sorted(records, key=lambda x: x.get("preco_draco",0), reverse=True)[:50]
    legendary_freq = defaultdict(int)
    for r in top_records:
        for item in r.get("legendary_items", []):
            legendary_freq[item] += 1

    stats["top_legendary_items"] = dict(sorted(legendary_freq.items(), key=lambda x: x[1], reverse=True)[:15])

    # Preço médio geral
    all_prices = [r["preco_draco"] for r in records if r.get("preco_draco")]
    if all_prices:
        stats["preco_medio_global"] = round(st.mean(all_prices))
        stats["preco_mediano_global"] = round(st.median(all_prices))

    return stats

def main():
    print("🚀 MIR4 Scraper iniciado:", datetime.now().strftime("%Y-%m-%d %H:%M"))

    # Recolher listas
    print("\n📋 A recolher listas...")
    recent = fetch_list("recent", pages=10)
    top = fetch_list("topTraded", pages=5)

    # Juntar e desduplicar por seq
    all_items = recent + top
    seen = set()
    unique = []
    for item in all_items:
        seq = item.get("info", {}).get("seq")
        if seq and seq not in seen:
            seen.add(seq)
            unique.append(item)

    print(f"\n🔍 A recolher detalhes de {len(unique)} NFTs...")
    records = []
    for i, item in enumerate(unique):
        nome = item.get("info",{}).get("characterName","?")
        print(f"  [{i+1}/{len(unique)}] {nome}")
        record = process_nft(item)
        records.append(record)

    # Guardar dados
    os.makedirs("data", exist_ok=True)

    # Histórico completo (mantém os últimos 500)
    history_path = "data/nft_history.json"
    try:
        with open(history_path) as f:
            history = json.load(f)
    except:
        history = []

    existing_seqs = {r["seq"] for r in history}
    new_records = [r for r in records if r["seq"] not in existing_seqs]
    history = (new_records + history)[:500]

    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    # Stats calculadas
    stats = compute_stats(history)
    with open("data/stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # Recentes (últimos 50 para o dashboard)
    with open("data/recent.json", "w", encoding="utf-8") as f:
        json.dump(records[:50], f, ensure_ascii=False, indent=2)

    print(f"\n✅ Concluído! {len(new_records)} novos NFTs. Total histórico: {len(history)}")

if __name__ == "__main__":
    main()
