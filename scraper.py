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
DEBUG_ENTRIES = []  # diagnóstico de falhas, escrito em data/debug_log.json no fim do run

def safe_int(x, default=0):
    """int() que não rebenta quando a API devolve null/None num campo que devia ser numérico."""
    try:
        return int(x)
    except (TypeError, ValueError):
        return default

def diag_endpoint(resp):
    if not isinstance(resp, dict):
        return "tipo_invalido"
    if "_fetch_error" in resp:
        return f"erro:{resp['_fetch_error']}"
    if not resp.get("data"):
        return "vazio"
    return "ok"

def get_info(item):
    """As listas 'recent'/'topTraded' embrulham os campos do NFT em item['info'];
    'sale'/'recommended' trazem os campos directamente no item, sem embrulho.
    Isto normaliza os dois formatos para o resto do código não ter de saber a diferença."""
    if not isinstance(item, dict):
        return {}
    return item.get("info", item)

def get(url, retries=3):
    last_err = None
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            return r.json()
        except Exception as e:
            last_err = str(e)
            time.sleep(2)
    # Distingue de uma resposta {} legítima: isto foi sempre excepção/timeout
    return {"_fetch_error": last_err or "unknown"}

def fetch_list(list_type="recent", pages=5):
    results = []
    for page in range(1, pages+1):
        url = f"{BASE}/nft/lists?listType={list_type}&page={page}&class=0&levMin=0&levMax=0&powerMin=0&powerMax=0&priceMin=0&priceMax=0&sort=latest&languageCode=pt"
        data = get(url)
        if page == 1:
            # Grava sempre a resposta bruta da 1ª página num ficheiro (não só no log do Actions,
            # que é difícil de consultar). Dá para ver directamente em
            # raw.githubusercontent.com/.../data/listfetch_debug.json sem entrar no GitHub.
            try:
                os.makedirs("data", exist_ok=True)
                with open("data/listfetch_debug.json", "r", encoding="utf-8") as f:
                    dbg = json.load(f)
            except Exception:
                dbg = {}
            dbg[list_type] = {
                "url": url,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "resposta_bruta": data
            }
            try:
                with open("data/listfetch_debug.json", "w", encoding="utf-8") as f:
                    json.dump(dbg, f, ensure_ascii=False, indent=2, default=str)
            except Exception as e:
                print(f"    (não consegui gravar listfetch_debug.json: {e})")
        items = data.get("data", {}).get("lists", [])
        if not items:
            if page == 1:
                if "_fetch_error" in data:
                    print(f"    ⚠️ fetch_list('{list_type}') falhou na página 1: {data['_fetch_error']}")
                elif "data" not in data:
                    print(f"    ⚠️ fetch_list('{list_type}') resposta inesperada: {str(data)[:200]}")
                else:
                    print(f"    ℹ️ fetch_list('{list_type}') devolveu 0 itens na página 1 (resposta ok, mas vazia)")
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
        # A API devolve o INVENTÁRIO TODO (mochila), não só o que está equipado — por isso
        # filtramos por mainType para ficar só com arma(2)/armadura(3)/acessório(4), que são
        # as únicas categorias claramente identificáveis como equipamento real nos dados reais
        # (as restantes — 5,6,7,8,9,17,21,None... — são poções, pedras mágicas, pergaminhos,
        # bilhetes e outros consumíveis/materiais, confirmado por inspecção directa dos nomes).
        EQUIP_MAIN_TYPES = {2, 3, 4}
        items = inven.get("data", [])
        equipados = []
        for i in items:
            g = str(i.get("grade",""))
            equipados.append({
                "nome": i.get("itemName",""),
                "grade": grade_map.get(g, g),
                "grade_id": safe_int(g) if g.isdigit() else 0,
                "enhance": i.get("enhance", 0),
                "mainType": i.get("mainType", 0),
                "tier": safe_int(i.get("tier", 0)),
                "hole_count": safe_int(i.get("holeCount", 0))
            })
        gear_only = [i for i in equipados if i.get("mainType") in EQUIP_MAIN_TYPES]
        legendary_items = [i["nome"] for i in gear_only if i["grade_id"] >= 5]
        epic_items = [i["nome"] for i in gear_only if i["grade_id"] == 4]

        # DIAGNÓSTICO TEMPORÁRIO: guardar o item em bruto (tal como a API o devolve, sem filtrar
        # campos) só para as peças de equipamento real (~5-10 por NFT, não o inventário todo).
        # Objectivo: descobrir se a API já devolve algum campo de "tier"/nível de item que ainda
        # não estamos a aproveitar, para além de grade+enhance. Remover depois de analisado.
        gear_raw_debug = [i for i in items if isinstance(i, dict) and i.get("mainType") in EQUIP_MAIN_TYPES]

        # Enhance (+N) do equipamento — factor de preço muito relevante e que faltava por completo:
        # dois NFTs com o mesmo Power Score e os mesmos itens podem valer o dobro só pela arma
        # estar em +11 em vez de +9 (custo de enhance cresce exponencialmente por nível no MIR4).
        gear_enhances = [i.get("enhance", 0) or 0 for i in gear_only]
        gear_avg_enhance = round(sum(gear_enhances)/len(gear_enhances), 1) if gear_enhances else 0
        gear_max_enhance = max(gear_enhances) if gear_enhances else 0
        weapon_enhance = max((i.get("enhance", 0) or 0 for i in gear_only if i.get("mainType") == 2), default=0)

        # Tier — confirmado com dados reais como campo INDEPENDENTE de grade (ex: grade "Raro"
        # aparece com tier 1, 2, 3 ou 4). Item raro de tier 4 pode valer mais que lendário tier 1.
        gear_tiers = [i["tier"] for i in gear_only]
        gear_max_tier = max(gear_tiers) if gear_tiers else 0
        gear_avg_tier = round(sum(gear_tiers)/len(gear_tiers), 1) if gear_tiers else 0

        # Soquetes por item (holeCount) — maioria dos itens tem 0, só alguns têm 1-3 preenchidos;
        # possivelmente o mesmo sistema de Primal Force mas ao nível do item em vez da conta.
        gear_total_holecount = sum(i["hole_count"] for i in gear_only)

        # --- SKILLS ---
        skill_list = skills.get("data", [])
        trained_skills = {s["skillName"]: safe_int(s.get("skillLevel",0)) for s in skill_list if safe_int(s.get("skillLevel",0)) > 0}
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
        if isinstance(equip_slots, dict):
            for slot, positions in equip_slots.items():
                if isinstance(positions, dict):
                    for pos, s in positions.items():
                        if isinstance(s, dict):
                            spirits_equipados.append({
                                "nome": s.get("petName",""),
                                "grade": s.get("grade",0),
                                "transcend": s.get("transcend",0),
                                "slot": safe_int(slot)
                            })
        spirits_lend = [s["nome"] for s in spirits_equipados if s["grade"] >= 5]
        spirits_grade6 = [s["nome"] for s in spirits_equipados if s["grade"] >= 6]
        spirits_inven = spirit_data.get("inven", []) if isinstance(spirit_data, dict) else []
        spirits_inven_lend = [s.get("petName","") for s in spirits_inven if isinstance(s,dict) and s.get("grade",0) >= 5]

        # --- BUILDINGS ---
        building_data = building.get("data", {})
        buildings = {}
        if isinstance(building_data, dict):
            for k, v in building_data.items():
                if isinstance(v, dict):
                    nome = v.get("buildingName","") or v.get("buildName","")
                    lv = safe_int(v.get("buildingLevel",0) or v.get("buildLv",0))
                    if nome: buildings[nome] = lv
        elif isinstance(building_data, list):
            for b in building_data:
                nome = b.get("buildingName","") or b.get("buildName","")
                lv = safe_int(b.get("buildingLevel",0) or b.get("buildLv",0))
                if nome: buildings[nome] = lv
        mina_lv = buildings.get("Mina", 0)

        # --- TRAINING ---
        training_data = training.get("data", {})
        training_summary = {}
        constituicao_lv = 0
        collect_lv = 0
        if isinstance(training_data, dict):
            for k, v in training_data.items():
                if isinstance(v, dict):
                    lv = safe_int(v.get("forceLevel", 0) or v.get("trainLv", 0))
                    nome = v.get("forceName", "") or v.get("trainName", "")
                    if lv > 0 and nome:
                        training_summary[nome] = lv
            constituicao_lv = safe_int(training_data.get("consitutionLevel", 0))
            collect_lv = safe_int(training_data.get("collectLevel", 0))
        elif isinstance(training_data, list):
            for t in training_data:
                lv = safe_int(t.get("forceLevel", 0) or t.get("trainLv", 0))
                nome = t.get("forceName", "") or t.get("trainName", "")
                if lv > 0 and nome:
                    training_summary[nome] = lv
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
            potencial_total = potential_data.get("total", 0) or potential_data.get("totalPotential", 0)
            potencial_caca = potential_data.get("hunting", 0) or potential_data.get("huntPotential", 0)
            potencial_pvp = potential_data.get("pvp", 0) or potential_data.get("pvpPotential", 0)
        else:
            potencial_total = potencial_caca = potencial_pvp = 0

        # --- SCRIPTURE ---
        scripture_data = scripture.get("data", {})
        scripture_summary = {}
        if isinstance(scripture_data, dict):
            for k, v in scripture_data.items():
                if isinstance(v, dict):
                    scripture_summary[v.get("codexName", k)] = {
                        "total": safe_int(v.get("totalCount",0)),
                        "completed": safe_int(v.get("completed",0))
                    }
        scripture_total_completed = sum(v.get("completed",0) for v in scripture_summary.values())

        # --- CODEX ---
        codex_data = codex.get("data", {})
        codex_summary = {}
        if isinstance(codex_data, dict):
            for k, v in codex_data.items():
                if isinstance(v, dict):
                    codex_summary[v.get("codexName", k)] = {
                        "total": safe_int(v.get("totalCount",0)),
                        "completed": safe_int(v.get("completed",0))
                    }
        codex_total_completed = sum(v.get("completed",0) for v in codex_summary.values())

        # --- HOLYSTUFF (Antiguidade) ---
        holystuff_data = holystuff.get("data", {})
        antiguidades = {}
        if isinstance(holystuff_data, dict):
            for k, v in holystuff_data.items():
                if isinstance(v, dict):
                    antiguidades[v.get("HolyStuffName",k)] = safe_int(v.get("Grade",0))
        antiguidade_max_grade = max(antiguidades.values()) if antiguidades else 0

        # --- DRAGON (Primal Force / Void Resonance) ---
        # HoleGrade = raridade do soquete; HoleCount = nº de pontos/atributos activados por soquete
        # ("mais pontos = mais atributos extra activados", como descrito pelo utilizador) — só o
        # grade máximo estava a ser aproveitado, o total de pontos (o que mais importa) nunca era.
        dragon_data = dragon.get("data", {})
        dragon_summary = {}
        if isinstance(dragon_data, dict):
            for k, v in dragon_data.items():
                if isinstance(v, dict):
                    dragon_summary[f"slot_{k}"] = {
                        "grade": safe_int(v.get("HoleGrade",0)),
                        "count": safe_int(v.get("HoleCount",0))
                    }
        dragon_max_grade = max((v["grade"] for v in dragon_summary.values()), default=0)
        dragon_total_count = sum(v["count"] for v in dragon_summary.values())
        dragon_max_count = max((v["count"] for v in dragon_summary.values()), default=0)

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
            training_block = heaven_data.get("training", {})
            if isinstance(training_block, dict):
                for slot, positions in training_block.items():
                    if isinstance(positions, dict):
                        for pos, t in positions.items():
                            if isinstance(t, dict):
                                lv = t.get("trainingLevel", 0)
                                if lv > 0:
                                    heaven_training[f"slot{slot}_pos{pos}"] = lv
        heaven_max_lv = max(heaven_training.values()) if heaven_training else 0
        circles = heaven_data.get("circle", {}) if isinstance(heaven_data, dict) else {}
        circles = circles if isinstance(circles, dict) else {}
        uniao_universal = {f"ciclo_{k}": v.get("circleValue",0) for k,v in circles.items() if isinstance(v,dict)}

        # --- SUCCESSION (Equip Transferência detalhado) ---
        succession_data = succession.get("data", {})
        equip_transferencia = {}
        succession_raw_debug = []
        if isinstance(succession_data, dict):
            equip_block = succession_data.get("equipItem", {})
            if isinstance(equip_block, dict):
                for slot, item in equip_block.items():
                    if isinstance(item, dict):
                        equip_transferencia[slot] = {
                            "nome": item.get("itemName",""),
                            "grade": safe_int(item.get("grade",0)),
                            "enhance": safe_int(item.get("enhance",0)),
                            "tier": safe_int(item.get("tier",0))
                        }
                        succession_raw_debug.append(item)
        succession_avg_enhance = round(sum(v["enhance"] for v in equip_transferencia.values()) / max(len(equip_transferencia),1), 1) if equip_transferencia else 0

        # Itens de Sucessão são equipamento real (arma/joias de um 2º conjunto) — juntam-se às
        # contagens de itens lendários/épicos do equipamento principal, em vez de ficarem de fora.
        succession_legendary = [v["nome"] for v in equip_transferencia.values() if v["grade"] >= 5]
        succession_epic = [v["nome"] for v in equip_transferencia.values() if v["grade"] == 4]
        succession_max_tier = max((v["tier"] for v in equip_transferencia.values()), default=0)

        # Juntar aos totais do equipamento principal — dois conjuntos de equipamento real, a
        # mesma pessoa. Antes disto, o de Sucessão ficava de fora das contagens de equivalência.
        legendary_items = legendary_items + succession_legendary
        epic_items = epic_items + succession_epic
        gear_max_tier = max(gear_max_tier, succession_max_tier)

        # Flag explícita: distingue "valor real é 0" de "ainda não sabemos".
        # Mesma condição usada em needs_update() — se nenhum destes veio preenchido,
        # o pedido aos endpoints de detalhe provavelmente falhou ou voltou vazio.
        dados_completos = bool(potencial_total or constituicao_lv or heaven_max_lv or succession_avg_enhance or mina_lv)

        if not dados_completos:
            DEBUG_ENTRIES.append({
                "transport_id": transport_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "endpoints": {
                    "potential": diag_endpoint(potential),
                    "spirit": diag_endpoint(spirit),
                    "heaven": diag_endpoint(heaven),
                    "succession": diag_endpoint(succession),
                    "building": diag_endpoint(building),
                    "training": diag_endpoint(training),
                    "inven": diag_endpoint(inven),
                }
            })

        return {
            "dados_completos": dados_completos,
            # Inventário
            "equipados": equipados,
            "legendary_items": legendary_items,
            "epic_items": epic_items,
            "legendary_count": len(legendary_items),
            "gear_avg_enhance": gear_avg_enhance,
            "gear_max_enhance": gear_max_enhance,
            "weapon_enhance": weapon_enhance,
            "gear_max_tier": gear_max_tier,
            "gear_avg_tier": gear_avg_tier,
            "gear_total_holecount": gear_total_holecount,
            "gear_raw_debug": gear_raw_debug,
            "succession_raw_debug": succession_raw_debug,
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
            "collect_lv": collect_lv,
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
            "dragon_total_count": dragon_total_count,
            "dragon_max_count": dragon_max_count,
            "scripture_total_completed": scripture_total_completed,
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
        DEBUG_ENTRIES.append({
            "transport_id": transport_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoints": {"excepcao_geral": str(e)}
        })
        return {
            "dados_completos": False,
            "equipados":[],"legendary_items":[],"epic_items":[],"legendary_count":0,"epic_count":0,
            "gear_avg_enhance":0,"gear_max_enhance":0,"weapon_enhance":0,
            "gear_max_tier":0,"gear_avg_tier":0,"gear_total_holecount":0,
            "trained_skills":{},"max_skill_lv":0,"mainstats":{},"all_stats":{},
            "spirits_equipados":[],"spirits_lend":[],"spirits_grade6":[],"spirits_lend_count":0,"spirits_grade6_count":0,"spirits_inven_lend":[],
            "buildings":{},"mina_lv":0,"training":{},"constituicao_lv":0,"collect_lv":0,
            "magicorb":{},"magicstone":{},"mystpiece":{},
            "potencial_total":0,"potencial_caca":0,"potencial_pvp":0,
            "scripture":{},"codex":{},"codex_total_completed":0,
            "antiguidades":{},"antiguidade_max_grade":0,
            "dragon":{},"dragon_max_grade":0,"dragon_total_count":0,"dragon_max_count":0,
            "scripture_total_completed":0,"recursos":{},
            "heaven_training":{},"heaven_max_lv":0,"uniao_universal":{},
            "equip_transferencia":{},"succession_avg_enhance":0,
        }

def process_nft(item, cached_detail=None):
    info = get_info(item)
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
        "row_id":       info.get("rowID", 0),
        "trade_dt":     trade_dt,
        "data_venda":   datetime.fromtimestamp(trade_dt, tz=timezone.utc).strftime("%Y-%m-%d %H:%M") if trade_dt else "",
        "scraped_at":   datetime.now(timezone.utc).isoformat()
    }

    agora = datetime.now(timezone.utc).isoformat()
    campos_proprios = set(record.keys()) | {"primeiro_visto", "ultima_vez_visto"}

    if cached_detail is not None:
        # NFT vendido que já tínhamos visto à venda: reaproveita o detalhe já recolhido nessa
        # altura em vez de voltar a pedir os 10 endpoints — poupa chamadas e é mais rápido.
        record.update({k: v for k, v in cached_detail.items() if k not in campos_proprios})
        record["primeira_tentativa"] = cached_detail.get("primeira_tentativa", agora)
        record["ultima_tentativa"] = agora
        record["tentativas"] = cached_detail.get("tentativas", 1)
        if cached_detail.get("dados_completos"):
            record["completo_em"] = cached_detail.get("completo_em", agora)
            record["tempo_ate_completar_h"] = cached_detail.get("tempo_ate_completar_h", 0.0)
        record["_reaproveitado_de_listagem"] = True
    elif transport_id:
        detail = fetch_detail(transport_id, class_id)
        record.update(detail)
        record["primeira_tentativa"] = agora
        record["ultima_tentativa"] = agora
        record["tentativas"] = 1
        if detail.get("dados_completos"):
            record["completo_em"] = agora
            record["tempo_ate_completar_h"] = 0.0
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

def needs_update(r):
    if not r.get("transport_id"):
        return False
    if "dados_completos" in r:
        return not r["dados_completos"]
    # Registos antigos sem a flag: heurística anterior
    return not r.get("potencial_total", 0) and not r.get("constituicao_lv", 0)

def main():
    print("🚀 MIR4 Scraper v3:", datetime.now().strftime("%Y-%m-%d %H:%M"))

    history_path = "data/nft_history.json"
    listings_path = "data/listings_active.json"
    try:
        with open(history_path, encoding="utf-8") as f:
            history = json.load(f)
    except:
        history = []
    try:
        with open(listings_path, encoding="utf-8") as f:
            listings_active = json.load(f)
    except:
        listings_active = []

    existing_seqs = {r["seq"] for r in history}
    listings_by_tid = {l["transport_id"]: l for l in listings_active if l.get("transport_id")}
    print(f"📦 Histórico actual: {len(history)} NFTs | 🏪 Listagens activas: {len(listings_active)}")

    print("📋 A recolher listas...")
    recent = fetch_list("recent", pages=8)
    top = fetch_list("topTraded", pages=3)
    recommended = fetch_list("recommended", pages=2)

    all_items = recent + top + recommended
    seen = set()
    unique_items = []
    for item in all_items:
        seq = get_info(item).get("seq")
        if seq and seq not in seen and seq not in existing_seqs:
            seen.add(seq)
            unique_items.append(item)

    print(f"🆕 {len(unique_items)} vendas novas para processar")

    new_records = []
    for i, item in enumerate(unique_items):
        info = get_info(item)
        tid = info.get("transportID")
        nome = info.get("characterName", "?")
        cached = listings_by_tid.get(tid)
        if cached and cached.get("dados_completos"):
            print(f"  [{i+1}/{len(unique_items)}] {nome} (reaproveitado da listagem)")
            record = process_nft(item, cached_detail=cached)
        else:
            print(f"  [{i+1}/{len(unique_items)}] {nome}")
            record = process_nft(item)
        new_records.append(record)

    history = (new_records + history)[:MAX_HISTORY]

    # Actualizar NFTs sem dados completos (máx 20 por run)
    to_update = [r for r in history if needs_update(r)][:20]
    if to_update:
        print(f"\n🔄 A actualizar {len(to_update)} NFTs incompletos...")
        for i, r in enumerate(to_update):
            print(f"  [{i+1}/{len(to_update)}] {r.get('nome','?')} (tentativa #{r.get('tentativas',0)+1})", end=" ... ")
            detail = fetch_detail(r["transport_id"], r.get("classe_id", 0))
            agora = datetime.now(timezone.utc).isoformat()
            idx = next((j for j,h in enumerate(history) if h.get("seq") == r.get("seq")), None)
            if idx is not None:
                history[idx]["tentativas"] = history[idx].get("tentativas", 0) + 1
                history[idx]["ultima_tentativa"] = agora
                history[idx].setdefault("primeira_tentativa", agora)
            if detail and detail.get("dados_completos"):
                if idx is not None:
                    history[idx].update(detail)
                    history[idx]["completo_em"] = agora
                    try:
                        t0 = datetime.fromisoformat(history[idx]["primeira_tentativa"])
                        t1 = datetime.fromisoformat(agora)
                        history[idx]["tempo_ate_completar_h"] = round((t1 - t0).total_seconds() / 3600, 2)
                    except Exception:
                        pass
                print(f"✅ pot:{detail.get('potencial_total',0)} const:{detail.get('constituicao_lv',0)}")
            else:
                print("❌")
            time.sleep(0.5)

    # ---- LISTAGENS À VENDA ----
    # Guarda o estado de quem está à venda AGORA, com o mesmo detalhe que já recolhemos para
    # vendas. Quando uma listagem desaparece e o mesmo transport_id aparece como venda nova,
    # os dados já recolhidos são reaproveitados acima (em vez de pedir tudo outra vez).
    print("\n🏪 A recolher listagens à venda...")
    sale_items = fetch_list("sale", pages=25)
    current_active_tids = set()
    sale_by_tid = {}
    for item in sale_items:
        tid = get_info(item).get("transportID")
        if tid:
            current_active_tids.add(tid)
            sale_by_tid[tid] = item

    sold_tid_set = {r.get("transport_id") for r in new_records if r.get("transport_id")}

    ainda_activas = []
    n_vendidas = n_desaparecidas = 0
    for l in listings_active:
        tid = l.get("transport_id")
        if tid in current_active_tids:
            item = sale_by_tid.get(tid)
            if item:
                l["preco_draco"] = get_info(item).get("price", l.get("preco_draco"))
            l["ultima_vez_visto"] = datetime.now(timezone.utc).isoformat()
            ainda_activas.append(l)
        elif tid in sold_tid_set:
            n_vendidas += 1  # já reaproveitado acima; só sai da lista de activas
        else:
            n_desaparecidas += 1  # delistado/cancelado — sai sem ir para o histórico de vendas

    novas_tids = current_active_tids - set(listings_by_tid.keys())
    novas_items = [it for it in sale_items if get_info(it).get("transportID") in novas_tids]
    MAX_NOVAS_LISTAGENS = 25  # tal como o backfill, para não rebentar rate-limit de uma vez
    print(f"🏪 {len(current_active_tids)} activas | {len(novas_items)} novas | {n_vendidas} venderam | {n_desaparecidas} desapareceram sem venda confirmada")

    for i, item in enumerate(novas_items[:MAX_NOVAS_LISTAGENS]):
        nome = get_info(item).get("characterName", "?")
        print(f"  [listagem {i+1}/{min(len(novas_items),MAX_NOVAS_LISTAGENS)}] {nome}")
        record = process_nft(item)
        agora = datetime.now(timezone.utc).isoformat()
        record["primeiro_visto"] = agora
        record["ultima_vez_visto"] = agora
        ainda_activas.append(record)

    # Backfill de listagens ainda sem dados completos (mesma lógica do histórico, ficheiro diferente)
    to_update_listings = [l for l in ainda_activas if needs_update(l)][:15]
    if to_update_listings:
        print(f"🔄 A actualizar {len(to_update_listings)} listagens incompletas...")
        for i, l in enumerate(to_update_listings):
            print(f"  [{i+1}/{len(to_update_listings)}] {l.get('nome','?')} (tentativa #{l.get('tentativas',0)+1})", end=" ... ")
            detail = fetch_detail(l["transport_id"], l.get("classe_id", 0))
            agora = datetime.now(timezone.utc).isoformat()
            idx = next((j for j, h in enumerate(ainda_activas) if h.get("transport_id") == l.get("transport_id")), None)
            if idx is not None:
                ainda_activas[idx]["tentativas"] = ainda_activas[idx].get("tentativas", 0) + 1
                ainda_activas[idx]["ultima_tentativa"] = agora
                ainda_activas[idx].setdefault("primeira_tentativa", agora)
                if detail and detail.get("dados_completos"):
                    ainda_activas[idx].update(detail)
                    ainda_activas[idx]["completo_em"] = agora
                    print(f"✅ pot:{detail.get('potencial_total',0)}")
                else:
                    print("❌")
            time.sleep(0.5)

    listings_active = ainda_activas[:1000]
    with open(listings_path, "w", encoding="utf-8") as f:
        json.dump(listings_active, f, ensure_ascii=False, indent=2)

    # Diagnóstico de falhas (últimas 300 entradas) — ver que endpoints estão a falhar e porquê
    if DEBUG_ENTRIES:
        debug_path = "data/debug_log.json"
        try:
            with open(debug_path, encoding="utf-8") as f:
                existing_debug = json.load(f)
        except Exception:
            existing_debug = []
        combined_debug = (DEBUG_ENTRIES + existing_debug)[:300]
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(combined_debug, f, ensure_ascii=False, indent=2)
        print(f"🩺 Diagnóstico: {len(DEBUG_ENTRIES)} falhas novas registadas em {debug_path}")

    os.makedirs("data", exist_ok=True)
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    with open("data/recent.json", "w", encoding="utf-8") as f:
        json.dump(history[:100], f, ensure_ascii=False, indent=2)

    stats = compute_stats(history)
    with open("data/stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"✅ +{len(new_records)} vendas novas | Total vendas: {len(history)} | Listagens activas: {len(listings_active)}")

if __name__ == "__main__":
    main()
