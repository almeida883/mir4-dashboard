"""
MIR4 NFT Scraper v3 — GitHub Actions
Recolhe todos os endpoints de detalhe de cada NFT
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
        # Recolher todos os endpoints
        ep = lambda name, extra="": get(f"{BASE}/nft/character/{name}?transportID={transport_id}&languageCode=pt{extra}")
        
        inven      = ep("inven")
        skills     = ep("skills", f"&class={class_id}")
        stats      = ep("stats")
        spirit     = ep("spirit")
        building   = ep("building")
        training   = ep("training")
        magicorb   = ep("magicorb")
        magicstone = ep("magicstone")
        mystpiece  = ep("mysticalpiece")
        potential  = ep("potential")
        scripture  = ep("scripture")
        codex      = ep("codex")
        holystuff  = ep("holystuff")
        dragon     = ep("dragon")
        assets     = ep("assets")
        heaven     = ep("heaven")
        succession = ep("succession")
        time.sleep(0.1)

        grade_map = {"6":"Mítico","5":"Lendário","4":"Épico","3":"Raro","2":"Incomum","1":"Normal"}

        # --- INVENTÁRIO (itens equipados) ---
        items = inven.get("data", [])
        equipados = []
        for i in items:
            g = str(i.get("grade",""))
            equipados.append({
                "nome": i.get("itemName",""),
                "grade": grade_map.get(g, g),
                "grade_id": int(g) if g.isdigit() else 0,
                "enhance": i.get("enhance", 0),
                "mainType": i.get("mainType", 0)
            })
        legendary_items = [i["nome"] for i in equipados if i["grade_id"] >= 5]
        epic_items = [i["nome"] for i in equipados if i["grade_id"] == 4]

        # --- SKILLS ---
        skill_list = skills.get("data", [])
        trained_skills = {s["skillName"]: int(s.get("skillLevel",0)) for s in skill_list if int(s.get("skillLevel",0)) > 0}
        max_skill_lv = max(trained_skills.values()) if trained_skills else 0

        # --- STATS ---
        mainstats = {}
        for s in stats.get("data", {}).get("mainstats", []):
            val = str(s.get("statValue","")).replace(",","").replace("%","")
            try: mainstats[s["statName"]] = float(val)
            except: mainstats[s["statName"]] = s.get("statValue","")
        all_stats = {}
        for s in stats.get("data", {}).get("lists", []):
            val = str(s.get("statValue","")).replace(",","").replace("%","").replace("sec","")
            try: all_stats[s["statName"]] = float(val)
            except: all_stats[s["statName"]] = s.get("statValue","")

        # --- SPIRITS ---
        spirit_data = spirit.get("data", {})
        equip_slots = spirit_data.get("equip", {}) if isinstance(spirit_data, dict) else {}
        spirits_equipados = []
        for slot, positions in equip_slots.items():
            if isinstance(positions, dict):
                for pos, s in positions.items():
                    if isinstance(s, dict):
                        spirits_equipados.append({
                            "nome": s.get("petName",""),
                            "grade": s.get("grade",0),
                            "transcend": s.get("transcend",0),
                            "slot": int(slot)
                        })
        spirits_lend = [s["nome"] for s in spirits_equipados if s["grade"] >= 5]
        spirits_grade6 = [s["nome"] for s in spirits_equipados if s["grade"] >= 6]
        spirits_inven = spirit_data.get("inven", []) if isinstance(spirit_data, dict) else []
        spirits_inven_lend = [s.get("petName","") for s in spirits_inven if isinstance(s,dict) and s.get("grade",0) >= 5]

        # --- BUILDINGS ---
        building_data = building.get("data", [])
        buildings = {}
        if isinstance(building_data, list):
            for b in building_data:
                buildings[b.get("buildName","")] = b.get("buildLv",0)
        elif isinstance(building_data, dict):
            for k,v in building_data.items():
                if isinstance(v, dict):
                    buildings[v.get("buildName", k)] = v.get("buildLv",0)
        mina_lv = buildings.get("Mina", 0)

        # --- TRAINING ---
        training_data = training.get("data", [])
        training_summary = {}
        if isinstance(training_data, list):
            for t in training_data:
                if t.get("trainLv",0) > 0:
                    training_summary[t.get("trainName","")] = t.get("trainLv",0)
        elif isinstance(training_data, dict):
            for k,v in training_data.items():
                if isinstance(v, dict) and v.get("trainLv",0) > 0:
                    training_summary[v.get("trainName",k)] = v.get("trainLv",0)
        constituicao_lv = training_summary.get("Constituição", 0)

        # --- MAGIC ORB ---
        magicorb_data = magicorb.get("data", [])
        magicorb_summary = {}
        if isinstance(magicorb_data, list):
            for m in magicorb_data:
                if m.get("orbLv",0) > 0:
                    magicorb_summary[m.get("orbName","")] = m.get("orbLv",0)
        elif isinstance(magicorb_data, dict):
            for slot, decks in magicorb_data.items():
                if isinstance(decks, dict):
                    for pos, m in decks.items():
                        if isinstance(m, dict) and m.get("orbName"):
                            magicorb_summary[m.get("orbName","")] = m.get("orbLv",0)

        # --- MAGIC STONE ---
        magicstone_data = magicstone.get("data", [])
        magicstone_summary = {}
        if isinstance(magicstone_data, list):
            for m in magicstone_data:
                if m.get("stoneLv",0) > 0:
                    magicstone_summary[m.get("stoneName","")] = m.get("stoneLv",0)
        elif isinstance(magicstone_data, dict):
            for slot, decks in magicstone_data.items():
                if isinstance(decks, dict):
                    for pos, m in decks.items():
                        if isinstance(m, dict):
                            magicstone_summary[m.get("stoneName","")] = m.get("stoneLv",0)

        # --- MYSTICAL PIECE ---
        mystpiece_data = mystpiece.get("data", [])
        mystpiece_summary = {}
        if isinstance(mystpiece_data, list):
            for m in mystpiece_data:
                mystpiece_summary[m.get("pieceName","")] = {"grade": m.get("grade",0), "enhance": m.get("enhance",0)}
        elif isinstance(mystpiece_data, dict):
            for slot, decks in mystpiece_data.items():
                if isinstance(decks, dict):
                    for pos, m in decks.items():
                        if isinstance(m, dict):
                            mystpiece_summary[m.get("pieceName","")] = {"grade": m.get("grade",0), "enhance": m.get("enhance",0)}

        # --- POTENTIAL ---
        potential_data = potential.get("data", {})
        if isinstance(potential_data, dict):
            potencial_total = potential_data.get("totalPotential", 0)
            potencial_caca = potential_data.get("huntPotential", 0)
            potencial_pvp = potential_data.get("pvpPotential", 0)
        else:
            potencial_total = potencial_caca = potencial_pvp = 0

        # --- SCRIPTURE ---
        scripture_data = scripture.get("data", {})
        scripture_summary = {}
        if isinstance(scripture_data, dict):
            for k, v in scripture_data.items():
                if isinstance(v, dict):
                    scripture_summary[v.get("codexName", k)] = {
                        "total": int(v.get("totalCount",0)),
                        "completed": int(v.get("completed",0))
                    }

        # --- CODEX ---
        codex_data = codex.get("data", {})
        codex_summary = {}
        if isinstance(codex_data, dict):
            for k, v in codex_data.items():
                if isinstance(v, dict):
                    codex_summary[v.get("codexName", k)] = {
                        "total": int(v.get("totalCount",0)),
                        "completed": int(v.get("completed",0))
                    }
        codex_total_completed = sum(v.get("completed",0) for v in codex_summary.values())

        # --- HOLYSTUFF (Antiguidade) ---
        holystuff_data = holystuff.get("data", {})
        antiguidades = {}
        if isinstance(holystuff_data, dict):
            for k, v in holystuff_data.items():
                if isinstance(v, dict):
                    antiguidades[v.get("HolyStuffName",k)] = int(v.get("Grade",0))
        antiguidade_max_grade = max(antiguidades.values()) if antiguidades else 0

        # --- DRAGON ---
        dragon_data = dragon.get("data", {})
        dragon_summary = {}
        if isinstance(dragon_data, dict):
            for k, v in dragon_data.items():
                if isinstance(v, dict):
                    dragon_summary[f"slot_{k}"] = {
                        "grade": int(v.get("HoleGrade",0)),
                        "count": int(v.get("HoleCount",0))
                    }
        dragon_max_grade = max((v["grade"] for v in dragon_summary.values()), default=0)

        # --- ASSETS (Recursos) ---
        assets_data = assets.get("data", {})
        recursos = {}
        if isinstance(assets_data, dict):
            for k, v in assets_data.items():
                if isinstance(v, dict):
                    recursos[v.get("assetName", k)] = v.get("assetValue", 0)

        # --- HEAVEN (Equip Transferência + União Universal) ---
        heaven_data = heaven.get("data", {})
        heaven_training = {}
        if isinstance(heaven_data, dict):
            for slot, positions in heaven_data.get("training", {}).items():
                if isinstance(positions, dict):
                    for pos, t in positions.items():
                        if isinstance(t, dict):
                            lv = t.get("trainingLevel", 0)
                            if lv > 0:
                                heaven_training[f"slot{slot}_pos{pos}"] = lv
        heaven_max_lv = max(heaven_training.values()) if heaven_training else 0
        circles = heaven_data.get("circle", {}) if isinstance(heaven_data, dict) else {}
        uniao_universal = {f"ciclo_{k}": v.get("circleValue",0) for k,v in circles.items() if isinstance(v,dict)}

        # --- SUCCESSION (Equip Transferência detalhado) ---
        succession_data = succession.get("data", {})
        equip_transferencia = {}
        if isinstance(succession_data, dict):
            for slot, item in succession_data.get("equipItem", {}).items():
                if isinstance(item, dict):
                    equip_transferencia[slot] = {
                        "nome": item.get("itemName",""),
                        "grade": int(item.get("grade",0)),
                        "enhance": int(item.get("enhance",0))
                    }
        succession_avg_enhance = round(sum(v["enhance"] for v in equip_transferencia.values()) / max(len(equip_transferencia),1), 1) if equip_transferencia else 0

        return {
            # Inventário
            "equipados": equipados,
            "legendary_items": legendary_items,
            "epic_items": epic_items,
            "legendary_count": len(legendary_items),
            "epic_count": len(epic_items),
            # Skills
            "trained_skills": trained_skills,
            "max_skill_lv": max_skill_lv,
            # Stats
            "mainstats": mainstats,
            "all_stats": all_stats,
            # Spirits
            "spirits_equipados": spirits_equipados,
            "spirits_lend": spirits_lend,
            "spirits_grade6": spirits_grade6,
            "spirits_lend_count": len(spirits_lend),
            "spirits_grade6_count": len(spirits_grade6),
            "spirits_inven_lend": spirits_inven_lend,
            # Buildings
            "buildings": buildings,
            "mina_lv": mina_lv,
            # Training
            "training": training_summary,
            "constituicao_lv": constituicao_lv,
            # Magic Orb
            "magicorb": magicorb_summary,
            # Magic Stone
            "magicstone": magicstone_summary,
            # Mystical Piece
            "mystpiece": mystpiece_summary,
            # Potential
            "potencial_total": potencial_total,
            "potencial_caca": potencial_caca,
            "potencial_pvp": potencial_pvp,
            # Scripture + Codex
            "scripture": scripture_summary,
            "codex": codex_summary,
            "codex_total_completed": codex_total_completed,
            # Holystuff (Antiguidade)
            "antiguidades": antiguidades,
            "antiguidade_max_grade": antiguidade_max_grade,
            # Dragon
            "dragon": dragon_summary,
            "dragon_max_grade": dragon_max_grade,
            # Assets
            "recursos": recursos,
            # Heaven
            "heaven_training": heaven_training,
            "heaven_max_lv": heaven_max_lv,
            "uniao_universal": uniao_universal,
            # Succession
            "equip_transferencia": equip_transferencia,
            "succession_avg_enhance": succession_avg_enhance,
        }
    except Exception as e:
        print(f"    Erro detalhe: {e}")
        return {
            "equipados":[],"legendary_items":[],"epic_items":[],"legendary_count":0,"epic_count":0,
            "trained_skills":{},"max_skill_lv":0,"mainstats":{},"all_stats":{},
            "spirits_equipados":[],"spirits_lend":[],"spirits_grade6":[],"spirits_lend_count":0,"spirits_grade6_count":0,"spirits_inven_lend":[],
            "buildings":{},"mina_lv":0,"training":{},"constituicao_lv":0,
            "magicorb":{},"magicstone":{},"mystpiece":{},
            "potencial_total":0,"potencial_caca":0,"potencial_pvp":0,
            "scripture":{},"codex":{},"codex_total_completed":0,
            "antiguidades":{},"antiguidade_max_grade":0,
            "dragon":{},"dragon_max_grade":0,"recursos":{},
            "heaven_training":{},"heaven_max_lv":0,"uniao_universal":{},
            "equip_transferencia":{},"succession_avg_enhance":0,
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
        time.sleep(0.3)

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

    from collections import defaultdict
    por_classe = defaultdict(list)
    for r in valid:
        if r.get("classe") != "?":
            por_classe[r["classe"]].append(r["preco_draco"])
    stats["por_classe"] = {
        c: {"media": round(st.mean(p)), "mediana": round(st.median(p)), "min": min(p), "max": max(p), "count": len(p)}
        for c, p in por_classe.items()
    }

    por_nivel = defaultdict(list)
    for r in valid:
        if r.get("nivel"):
            b = (r["nivel"] // 10) * 10
            por_nivel[b].append(r["preco_draco"])
    stats["por_nivel"] = {
        str(b): {"media": round(st.mean(p)), "mediana": round(st.median(p)), "count": len(p)}
        for b, p in sorted(por_nivel.items())
    }

    por_ps = defaultdict(list)
    for r in valid:
        if r.get("power_score"):
            b = (r["power_score"] // 100000) * 100000
            por_ps[b].append(r["preco_draco"])
    stats["por_ps"] = {
        str(b): {"media": round(st.mean(p)), "mediana": round(st.median(p)), "count": len(p)}
        for b, p in sorted(por_ps.items())
    }

    # Spirits lendários mais frequentes nos NFTs caros (top 20%)
    top = sorted(valid, key=lambda x: x["preco_draco"], reverse=True)[:max(1, len(valid)//5)]
    from collections import Counter
    spirit_freq = Counter()
    for r in top:
        for s in r.get("spirits_lend", []):
            spirit_freq[s] += 1
    stats["top_spirits"] = dict(spirit_freq.most_common(15))

    leg_freq = Counter()
    for r in top:
        for i in r.get("legendary_items", []):
            leg_freq[i] += 1
    stats["top_legendary_items"] = dict(leg_freq.most_common(15))

    return stats

def main():
    print("🚀 MIR4 Scraper v3:", datetime.now().strftime("%Y-%m-%d %H:%M"))

    history_path = "data/nft_history.json"
    try:
        with open(history_path, encoding="utf-8") as f:
            history = json.load(f)
    except:
        history = []

    existing_seqs = {r["seq"] for r in history}
    print(f"📦 Histórico actual: {len(history)} NFTs")

    print("📋 A recolher listas...")
    recent = fetch_list("recent", pages=8)
    top = fetch_list("topTraded", pages=3)
    recommended = fetch_list("recommended", pages=2)

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

    history = (new_records + history)[:MAX_HISTORY]

    os.makedirs("data", exist_ok=True)
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    with open("data/recent.json", "w", encoding="utf-8") as f:
        json.dump(history[:100], f, ensure_ascii=False, indent=2)

    stats = compute_stats(history)
    with open("data/stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"✅ +{len(new_records)} novos | Total: {len(history)}")

if __name__ == "__main__":
    main()
