"""
MIR4 NFT Scraper v2 — GitHub Actions
Corre de 10 em 10 minutos via cron
"""
import requests, json, time, os
from datetime import datetime, timezone

BASE = "https://webapi.mir4global.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    "Referer": "https://www.xdraco.com/"
}
CLASS_MAP = {1:"Warrior",2:"Sorcerer",3:"Taoist",4:"Arbalist",5:"Lancer",6:"Darkist"}
MAX_HISTORY = 2000

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
        time.sleep(0.3)
    return results

def fetch_detail(transport_id, class_id):
    try:
        inven = get(f"{BASE}/nft/character/inven?transportID={transport_id}&languageCode=pt")
        skills = get(f"{BASE}/nft/character/skills?transportID={transport_id}&class={class_id}&languageCode=pt")
        stats = get(f"{BASE}/nft/character/stats?transportID={transport_id}&languageCode=pt")

        items = inven.get("data", [])
        grade_map = {"5":"Lendário","4":"Épico","3":"Raro","2":"Incomum","1":"Normal"}
        
        equipados = []
        for i in items:
            g = str(i.get("grade",""))
            equipados.append({
                "nome": i.get("itemName",""),
                "grade": grade_map.get(g, g),
                "grade_id": int(g) if g.isdigit() else 0,
                "enhance": i.get("enhance", 0),
                "slot": i.get("mainType", 0)
            })

        legendary = [i["nome"] for i in equipados if i["grade_id"] >= 4]
        epic = [i["nome"] for i in equipados if i["grade_id"] == 3]

        skill_list = skills.get("data", [])
        trained_skills = {s["skillName"]: int(s.get("skillLevel",0)) for s in skill_list if int(s.get("skillLevel",0)) > 0}

        mainstats = {}
        for s in stats.get("data", {}).get("mainstats", []):
            val = s["statValue"].replace(",","").replace("%","")
            try:
                mainstats[s["statName"]] = float(val)
            except:
                mainstats[s["statName"]] = s["statValue"]

        all_stats = {}
        for s in stats.get("data", {}).get("lists", []):
            val = s["statValue"].replace(",","").replace("%","").replace("sec","")
            try:
                all_stats[s["statName"]] = float(val)
            except:
                all_stats[s["statName"]] = s["statValue"]

        return {
            "equipados": equipados,
            "legendary_items": legendary,
            "epic_items": epic,
            "legendary_count": len(legendary),
            "epic_count": len(epic),
            "trained_skills": trained_skills,
            "mainstats": mainstats,
            "all_stats": all_stats
        }
    except Exception as e:
        print(f"    Erro detalhe: {e}")
        return {"equipados":[],"legendary_items":[],"epic_items":[],"legendary_count":0,"epic_count":0,"trained_skills":{},"mainstats":{},"all_stats":{}}

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
        "mirage_score": info.get("MirageScore", 0),
        "mira_x":       info.get("MiraX", 0),
        "servidor":     info.get("worldName",""),
        "trade_dt":     trade_dt,
        "data_venda":   datetime.fromtimestamp(trade_dt, tz=timezone.utc).strftime("%Y-%m-%d %H:%M") if trade_dt else "",
        "scraped_at":   datetime.now(timezone.utc).isoformat()
    }

    if transport_id:
        detail = fetch_detail(transport_id, class_id)
        record.update(detail)
        time.sleep(0.25)

    return record

def compute_stats(records):
    from collections import defaultdict
    import statistics as st

    valid = [r for r in records if r.get("preco_draco")]
    if not valid:
        return {"updated_at": datetime.now(timezone.utc).isoformat(), "total": 0}

    stats = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(records),
        "preco_medio_global": round(st.mean(r["preco_draco"] for r in valid)),
        "preco_mediano_global": round(st.median(r["preco_draco"] for r in valid))
    }

    # Por classe
    por_classe = defaultdict(list)
    for r in valid:
        if r.get("classe") != "?":
            por_classe[r["classe"]].append(r["preco_draco"])
    stats["por_classe"] = {
        c: {"media": round(st.mean(p)), "mediana": round(st.median(p)), "min": min(p), "max": max(p), "count": len(p)}
        for c, p in por_classe.items()
    }

    # Por nível
    por_nivel = defaultdict(list)
    for r in valid:
        if r.get("nivel"):
            b = (r["nivel"] // 10) * 10
            por_nivel[b].append(r["preco_draco"])
    stats["por_nivel"] = {
        str(b): {"media": round(st.mean(p)), "mediana": round(st.median(p)), "count": len(p)}
        for b, p in sorted(por_nivel.items())
    }

    # Por PS
    por_ps = defaultdict(list)
    for r in valid:
        if r.get("power_score"):
            b = (r["power_score"] // 100000) * 100000
            por_ps[b].append(r["preco_draco"])
    stats["por_ps"] = {
        str(b): {"media": round(st.mean(p)), "mediana": round(st.median(p)), "count": len(p)}
        for b, p in sorted(por_ps.items())
    }

    # Itens lendários mais frequentes nos top 20%
    top_records = sorted(valid, key=lambda x: x["preco_draco"], reverse=True)[:max(1, len(valid)//5)]
    leg_freq = defaultdict(int)
    for r in top_records:
        for item in r.get("legendary_items", []):
            leg_freq[item] += 1
    stats["top_legendary_items"] = dict(sorted(leg_freq.items(), key=lambda x: x[1], reverse=True)[:20])

    return stats

def main():
    print("🚀 MIR4 Scraper v2:", datetime.now().strftime("%Y-%m-%d %H:%M"))

    # Carregar histórico existente
    history_path = "data/nft_history.json"
    try:
        with open(history_path, encoding="utf-8") as f:
            history = json.load(f)
    except:
        history = []

    existing_seqs = {r["seq"] for r in history}
    print(f"📦 Histórico actual: {len(history)} NFTs")

    # Recolher listas
    print("📋 A recolher listas...")
    recent = fetch_list("recent", pages=8)
    top = fetch_list("topTraded", pages=3)
    recommended = fetch_list("recommended", pages=3)

    all_items = recent + top + recommended
    seen = set()
    unique_items = []
    for item in all_items:
        seq = item.get("info", {}).get("seq")
        if seq and seq not in seen and seq not in existing_seqs:
            seen.add(seq)
            unique_items.append(item)

    print(f"🆕 {len(unique_items)} NFTs novos para processar")

    new_records = []
    for i, item in enumerate(unique_items):
        nome = item.get("info",{}).get("characterName","?")
        print(f"  [{i+1}/{len(unique_items)}] {nome}")
        record = process_nft(item)
        new_records.append(record)

    # Actualizar histórico
    history = (new_records + history)[:MAX_HISTORY]

    os.makedirs("data", exist_ok=True)
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    # Recentes (últimos 100)
    with open("data/recent.json", "w", encoding="utf-8") as f:
        json.dump(history[:100], f, ensure_ascii=False, indent=2)

    # Stats
    stats = compute_stats(history)
    with open("data/stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"✅ +{len(new_records)} novos | Total: {len(history)}")

if __name__ == "__main__":
    main()
