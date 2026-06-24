# MIR4 NFT Dashboard

Dashboard automático que recolhe e analisa NFTs vendidos no xDraco.

## Setup (5 minutos)

### 1. Criar repositório no GitHub
- Vai a github.com → New repository
- Nome: `mir4-dashboard`
- Público (necessário para GitHub Pages)

### 2. Fazer upload dos ficheiros
```
mir4-dashboard/
├── .github/workflows/scraper.yml
├── scraper.py
├── data/          (criado automaticamente)
└── docs/
    └── index.html
```

### 3. Activar GitHub Pages
- Settings → Pages → Source: `Deploy from branch`
- Branch: `main`, Folder: `/docs`
- Guardar → o site fica em: `https://SEU_USER.github.io/mir4-dashboard`

### 4. Actualizar o URL no index.html
No ficheiro `docs/index.html`, linha:
```js
const BASE = 'https://raw.githubusercontent.com/SEU_USER/SEU_REPO/main/data/';
```
Substitui `SEU_USER` e `SEU_REPO` pelo teu utilizador e nome do repo.

### 5. Correr o scraper pela primeira vez
- Actions → `MIR4 NFT Scraper` → `Run workflow`

## Funcionamento
- Corre automaticamente de **2 em 2 horas**
- Recolhe últimas vendas + top traded
- Para cada NFT vai buscar itens, skills e stats
- Guarda histórico de até 500 NFTs
- GitHub Pages actualiza o site automaticamente
