"""
MIR4 NFT History Updater
Vai buscar detalhes em falta nos NFTs do histórico que foram recolhidos pelo scraper v1/v2
Corre uma vez: python update_history.py
"""
import requests, json, time
from datetime import datetime, timezone

BASE = "https://webapi.mir4global.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    "Referer": "https://www.xdraco.com/"
}

def get(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            return r.json()
        except:
            time.sleep(2)
    return {}

def fetch_detail(transport_id, class_id):
    try:
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
        holystuff  = ep("holystuff")
        dragon     = ep("dragon")
        assets     = ep("assets")
        heaven     = ep("heaven")
        succession = ep("succession")
        time.sleep(0.1)

        grade_map = {"6":"Mítico","5":"Lendário","4":"Épico","3":"Raro","2":"Incomum","1":"Normal"}

        # INVENTÁRIO
        items = inven.get("data", [])
        equipados = []
        for i in items:
            g = str(i.get("grade",""))
            equipados.append({"nome":i.get("itemName",""),"grade":grade_map.get(g,g),"grade_id":int(g) if g.isdigit() else 0,"enhance":i.get("enhance",0),"mainType":i.get("mainType",0)})
        legendary_items = [i["nome"] for i in equipados if i["grade_id"] >= 5]
        epic_items = [i["nome"] for i in equipados if i["grade_id"] == 4]

        # SKILLS
        skill_list = skills.get("data", [])
        trained_skills = {s["skillName"]: int(s.get("skillLevel",0)) for s in skill_list if int(s.get("skillLevel",0)) > 0}
        max_skill_lv = max(trained_skills.values()) if trained_skills else 0

        # STATS
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

        # SPIRITS
        spirit_data = spirit.get("data", {})
        equip_slots = spirit_data.get("equip", {}) if isinstance(spirit_data, dict) else {}
        spirits_equipados = []
        for slot, positions in equip_slots.items():
            if isinstance(positions, dict):
                for pos, s in positions.items():
                    if isinstance(s, dict):
                        spirits_equipados.append({"nome":s.get("petName",""),"grade":s.get("grade",0),"transcend":s.get("transcend",0),"slot":int(slot)})
        spirits_lend = [s["nome"] for s in spirits_equipados if s["grade"] >= 5]
        spirits_grade6 = [s["nome"] for s in spirits_equipados if s["grade"] >= 6]
        spirits_inven = spirit_data.get("inven", []) if isinstance(spirit_data, dict) else []
        spirits_inven_lend = [s.get("petName","") for s in spirits_inven if isinstance(s,dict) and s.get("grade",0) >= 5]

        # BUILDINGS
        building_data = building.get("data", [])
        buildings = {}
        if isinstance(building_data, list):
            for b in building_data: buildings[b.get("buildName","")] = b.get("buildLv",0)
        elif isinstance(building_data, dict):
            for k,v in building_data.items():
                if isinstance(v, dict): buildings[v.get("buildName",k)] = v.get("buildLv",0)
        mina_lv = buildings.get("Mina", 0)

        # TRAINING
        training_data = training.get("data", [])
        training_summary = {}
        if isinstance(training_data, list):
            for t in training_data:
                if t.get("trainLv",0) > 0: training_summary[t.get("trainName","")] = t.get("trainLv",0)
        elif isinstance(training_data, dict):
            for k,v in training_data.items():
                if isinstance(v, dict) and v.get("trainLv",0) > 0: training_summary[v.get("trainName",k)] = v.get("trainLv",0)
        constituicao_lv = training_summary.get("Constituição", 0)

        # POTENTIAL
        potential_data = potential.get("data", {})
        potencial_total = potential_data.get("totalPotential", 0) if isinstance(potential_data, dict) else 0
        potencial_caca = potential_data.get("huntPotential", 0) if isinstance(potential_data, dict) else 0
        potencial_pvp = potential_data.get("pvpPotential", 0) if isinstance(potential_data, dict) else 0

        # HOLYSTUFF
        holystuff_data = holystuff.get("data", {})
        antiguidades = {}
        if isinstance(holystuff_data, dict):
            for k,v in holystuff_data.items():
                if isinstance(v, dict): antiguidades[v.get("HolyStuffName",k)] = int(v.get("Grade",0))
        antiguidade_max_grade = max(antiguidades.values()) if antiguidades else 0

        # DRAGON
        dragon_data = dragon.get("data", {})
        dragon_summary = {}
        if isinstance(dragon_data, dict):
            for k,v in dragon_data.items():
                if isinstance(v, dict): dragon_summary[f"slot_{k}"] = {"grade":int(v.get("HoleGrade",0)),"count":int(v.get("HoleCount",0))}
        dragon_max_grade = max((v["grade"] for v in dragon_summary.values()), default=0)

        # ASSETS
        assets_data = assets.get("data", {})
        recursos = {}
        if isinstance(assets_data, dict):
            for k,v in assets_data.items():
                if isinstance(v, dict): recursos[v.get("assetName",k)] = v.get("assetValue",0)

        # HEAVEN
        heaven_data = heaven.get("data", {})
        heaven_training = {}
        if isinstance(heaven_data, dict):
            for slot, positions in heaven_data.get("training", {}).items():
                if isinstance(positions, dict):
                    for pos, t in positions.items():
                        if isinstance(t, dict):
                            lv = t.get("trainingLevel", 0)
                            if lv > 0: heaven_training[f"slot{slot}_pos{pos}"] = lv
        heaven_max_lv = max(heaven_training.values()) if heaven_training else 0
        circles = heaven_data.get("circle", {}) if isinstance(heaven_data, dict) else {}
        uniao_universal = {f"ciclo_{k}": v.get("circleValue",0) for k,v in circles.items() if isinstance(v,dict)}

        # SUCCESSION
        succession_data = succession.get("data", {})
        equip_transferencia = {}
        if isinstance(succession_data, dict):
            for slot, item in succession_data.get("equipItem", {}).items():
                if isinstance(item, dict):
                    equip_transferencia[slot] = {"nome":item.get("itemName",""),"grade":int(item.get("grade",0)),"enhance":int(item.get("enhance",0))}
        succession_avg_enhance = round(sum(v["enhance"] for v in equip_transferencia.values()) / max(len(equip_transferencia),1), 1) if equip_transferencia else 0

        return {
            "equipados": equipados, "legendary_items": legendary_items, "epic_items": epic_items,
            "legendary_count": len(legendary_items), "epic_count": len(epic_items),
            "trained_skills": trained_skills, "max_skill_lv": max_skill_lv,
            "mainstats": mainstats, "all_stats": all_stats,
            "spirits_equipados": spirits_equipados, "spirits_lend": spirits_lend,
            "spirits_grade6": spirits_grade6, "spirits_lend_count": len(spirits_lend),
            "spirits_grade6_count": len(spirits_grade6), "spirits_inven_lend": spirits_inven_lend,
            "buildings": buildings, "mina_lv": mina_lv,
            "training": training_summary, "constituicao_lv": constituicao_lv,
            "potencial_total": potencial_total, "potencial_caca": potencial_caca, "potencial_pvp": potencial_pvp,
            "antiguidades": antiguidades, "antiguidade_max_grade": antiguidade_max_grade,
            "dragon": dragon_summary, "dragon_max_grade": dragon_max_grade,
            "recursos": recursos, "heaven_training": heaven_training, "heaven_max_lv": heaven_max_lv,
            "uniao_universal": uniao_universal, "equip_transferencia": equip_transferencia,
            "succession_avg_enhance": succession_avg_enhance,
        }
    except Exception as e:
        print(f"    Erro: {e}")
        return None

def needs_update(r):
    # NFT precisa de update se não tem dados de spirits ou buildings
    return not r.get("spirits_equipados") and not r.get("buildings") and r.get("transport_id")

def main():
    print("🔄 MIR4 History Updater")
    print("=" * 50)

    with open("data/nft_history.json", encoding="utf-8") as f:
        history = json.load(f)

    to_update = [r for r in history if needs_update(r)]
    print(f"Total no histórico: {len(history)}")
    print(f"A actualizar: {len(to_update)} NFTs sem dados completos")

    updated = 0
    failed = 0
    for i, r in enumerate(to_update):
        print(f"  [{i+1}/{len(to_update)}] {r.get('nome','?')} | Nv{r.get('nivel')} | PS {r.get('power_score',0):,}", end=" ... ")
        detail = fetch_detail(r["transport_id"], r.get("classe_id", 0))
        if detail:
            idx = next((j for j,h in enumerate(history) if h.get("seq") == r.get("seq")), None)
            if idx is not None:
                history[idx].update(detail)
                updated += 1
                print(f"✅ spirits: {len(detail.get('spirits_lend',[]))}, mina: {detail.get('mina_lv',0)}")
        else:
            failed += 1
            print("❌ sem dados (NFT já não disponível)")
        time.sleep(0.5)

    with open("data/nft_history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Concluído! {updated} actualizados | {failed} sem dados disponíveis")
    print("Faz upload do data/nft_history.json para o GitHub")

if __name__ == "__main__":
    main()
