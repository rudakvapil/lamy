# 🦙 Fantasy Lamy z Panamy – Web

Statistický web pro FPL mini-ligu #83735.
Data se automaticky aktualizují každou hodinu přes GitHub Actions.

---

## 🚀 Jednorázový setup (~15 minut)

### Krok 1 – Vytvoř GitHub účet
Jdi na [github.com](https://github.com) a zaregistruj se (zdarma).

### Krok 2 – Vytvoř nový repozitář
1. Klikni na zelené tlačítko **"New"** (vlevo nahoře)
2. Název: `lamy-z-panamy` (nebo cokoliv)
3. Nastav jako **Public** (nutné pro GitHub Pages zdarma)
4. Klikni **"Create repository"**

### Krok 3 – Nahraj soubory
Nejjednodušší způsob – přes web:
1. V repozitáři klikni **"uploading an existing file"**
2. Přetáhni VŠECHNY soubory a složky z tohoto zipu:
   ```
   index.html
   data/season.json
   scripts/fetch_data.py
   .github/workflows/fetch_data.yml
   ```
3. Klikni **"Commit changes"**

> ⚠️ Důležité: Složky `.github/workflows/` musíš nahrát jako soubor s cestou.
> GitHub při uploadu zachová strukturu složek automaticky.

### Krok 4 – Zapni GitHub Pages
1. Jdi do **Settings** (záložka nahoře v repozitáři)
2. Vlevo klikni **"Pages"**
3. Pod "Source" vyber **"Deploy from a branch"**
4. Branch: **main**, složka: **/ (root)**
5. Klikni **"Save"**
6. Za ~2 minuty bude web dostupný na adrese:
   `https://TVOJE-UZIVATELSKE-JMENO.github.io/lamy-z-panamy/`

### Krok 5 – Spusť první stažení dat
1. Jdi na záložku **"Actions"** v repozitáři
2. Vlevo klikni na **"Fetch FPL Data"**
3. Vpravo klikni **"Run workflow"** → **"Run workflow"**
4. Počkej ~30 sekund, refresh stránky
5. Uvidíš zelený check ✅ – data jsou stažena!

### Krok 6 – Hotovo! 🎉
Od teď se data aktualizují **každou hodinu automaticky**.
Web je živý, sdílej odkaz s klukama.

---

## 🔧 Příští sezóna (2025/26)

Stačí upravit 2 soubory:

### 1. `scripts/fetch_data.py` – změň liga ID a hráče
```python
LEAGUE_ID = 83735        # ← změň na ID nové sezóny
CURRENT_SEASON = "2025/26"  # ← aktualizuj

PLAYERS = {
    4239832: {"name": "Martin Holub", ...},
    # ... případně přidej/odeber hráče
}
```

### 2. `index.html` – aktualizuj archiv
Najdi v souboru `const HISTORY = [` a přidej výsledek letošní sezóny.

To je vše – Actions poběží dál automaticky se stejným rozvrhem.

---

## 📁 Struktura projektu

```
lamy-z-panamy/
├── index.html              # Hlavní web (čte data/season.json)
├── data/
│   └── season.json         # Automaticky generovaná data (GitHub Actions)
├── scripts/
│   └── fetch_data.py       # Python skript – stahuje FPL API
└── .github/
    └── workflows/
        └── fetch_data.yml  # GitHub Actions – rozvrh spouštění
```

---

## ⚙️ Jak to funguje

```
Každou hodinu:
GitHub Actions → spustí fetch_data.py → stáhne FPL API → uloží data/season.json → pushne do repozitáře

Když otevřeš web:
index.html → načte data/season.json → zobrazí aktuální tabulku, playoff, statistiky
```

---

## 🆘 Troubleshooting

**Actions neběží:**
- Zkontroluj záložku "Actions" – je povolena?
- Jdi Settings → Actions → General → "Allow all actions"

**Web zobrazuje stará data:**
- Stiskni Ctrl+Shift+R (tvrdý refresh)
- Zkontroluj že Actions proběhl úspěšně (zelený check)

**FPL API vrací chybu:**
- FPL API je občas nedostupné – Actions to zkusí znovu za hodinu
- Mimo sezónu (červen–srpen) FPL mění strukturu API

---

## 📞 Kontakt

Problémy s webem? Napiš Claudovi 🦙

---

## 🌐 Vlastní hosting na webglobe.cz

Máš vlastní hosting? Super – web funguje jako čistý statický soubor.

### Jak to nasadit na webglobe.cz

**Krok 1 – GitHub Actions stále stahuje data**
GitHub Actions poběží dál na GitHubu a bude generovat `data/season.json`.

**Krok 2 – Nahraj soubory na webglobe FTP**
Do kořenového adresáře webu (nebo podsložky) nahraj:
```
index.html
data/season.json
```

**Krok 3 – Automatický upload přes GitHub Actions**
Přidej do `fetch_data.yml` krok který po vygenerování dat uploadne soubory na FTP:

```yaml
- name: Upload na webglobe FTP
  uses: SamKirkland/FTP-Deploy-Action@v4.3.4
  with:
    server: ftp.webglobe.cz
    username: ${{ secrets.FTP_USER }}
    password: ${{ secrets.FTP_PASS }}
    local-dir: ./
    server-dir: /public_html/lamy/   # uprav cestu
    include: |
      index.html
      data/**
```

Credentials ulož jako GitHub Secrets (Settings → Secrets → New repository secret):
- `FTP_USER` = tvůj FTP login
- `FTP_PASS` = tvůj FTP heslo

### Heslo na web

Webglobe podporuje `.htaccess` ochranu heslem.
Vytvoř soubory `.htaccess` a `.htpasswd` v adresáři webu:

**.htaccess:**
```
AuthType Basic
AuthName "Fantasy Lamy z Panamy"
AuthUserFile /home/UZIVATEL/public_html/lamy/.htpasswd
Require valid-user
```

**.htpasswd** (vygeneruj heslo příkazem nebo online generátorem):
```
lamy:$apr1$xyz$hashedpassword
```

Heslo vygeneruješ na: https://www.htaccesstools.com/htpasswd-generator/
