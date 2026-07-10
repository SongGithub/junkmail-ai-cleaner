# Spam Patterns — Outlook Junk Mail Analysis

**Last updated:** 2026-05-19  
**Source:** Live analysis of junk folder during cleanup run (~700+ emails processed)  
**Account:** jin-1234@live.com

---

## Matched Patterns (currently in script)

Sorted by frequency across the cleanup run so far.

| Category | Keywords | Volume | Notes |
|---|---|---|---|
| eharmony | eharmony, Offer | 65 | **Highest volume.** Sender identity spoofed by affiliate network — unrelated ads (windows, meals, therapy, AARP) sent under eharmony's name |
| Renewal by Andersen | Renewal by Andersen, windows | 23 | Window replacement ads |
| TruGreen | TruGreen | 23 | Lawn care service |
| Roof | Roof, roofing | 21 | Metal roof replacement |
| Healthcare.com | Healthcare.com | 16 | ACA/health insurance marketplace |
| CarShield | CarShield | 15 | Auto warranty |
| Optima Tax | Optima Tax, Tax Relief | 15 | IRS debt relief |
| Easy Canvas | Easy Canvas, Canvas Prints | 12 | Photo canvas printing |
| National Debt Relief | National Debt Relief, NationalDebt | 11 | Debt consolidation |
| Warby Parker | WarbyParker, Warby | 11 | Eyeglasses |
| LendingForAll | LendingForAll | 11 | Loan matching |
| LifeLine | LifeLine, Life Line Screening | 10 | Cardiovascular disease screenings |
| LaserAway | LaserAway | 9 | Laser hair removal |
| Orangetheory Fitness | Orangetheory, FREE Class, gym | 9 | Fitness class offers — relay: fittruex@momentzenith.com |
| Endurance Auto | Endurance Auto | 6 | Auto warranty (rival to CarShield) |
| Liberty Mutual | Liberty Mutual | 6 | Auto/home insurance |
| Hearing Aid | Hearing Aid, hear.com, soundlift | 6 | OTC hearing aids |
| American Home Shield | American Home Shield, home warranty | 5 | Home warranty |
| PhotoStick | PhotoStick, Omni | 4 | Photo backup device |
| Blissy | Blissy, pillowcase, sheets, sleep | 4+ | Luxury bedding — multiple relay domains (private@micpai.com, dreamgoal@eagercapital.com) |
| Ethos | Ethos Life | 3 | Life insurance |
| VSP | VSP, Vision Plans | 2 | Vision insurance |
| Lexington Law | Lexington Law | 1 | Credit repair |
| Destiny Mastercard | Destiny Mastercard, cashback rewards | 2 | Credit card offer — relay domain: pulsecertain.com |
| TRA Services (Tax Debt) | TRA Services, debtcarefree | 1 | Tax debt resolution — relay: comebeach.com |
| Brinks Home (Security) | Brinks Home, home security, free installation | 1 | Home security system — relay: lanitem.com |
| Rate Equity (HELOC) | Rate Equity, home equity, home's equity, HELOC | 2+ | Home equity loan — multiple sender variants, relay domains vary |
| TheCapitalWallet | TheCapitalWallet, Capital Wallet, smartcreditsecurepro | 1 | Loan/financial services marketplace — relay: tollharsh.com |
| NorthStar-Loans | NorthStar-Loans, northstar-loans.com | 1 | Personal loan matching — relay: masspetty.com |
| UsaWildSeaFood | UsaWildSeaFood, usawildseafood.com, seafood | 1+ | Gourmet seafood delivery — relay: mishresilient.info |
| Telstra | Telstra (catches WiFi Booster, Deals, and other variants) | 2+ | Regional (AU) tech spam — multiple variants from different relay domains |
| ForkFulMeals | ForkFulMeals, meal delivery, chef | 1 | Meal prep/delivery — relay: henryfluns.com |
| Keranique | Keranique, hair loss, Hair Fights | 4+ | Hair loss treatment — relay: folliclerebirthcare@mapdefensive.com |
| Miracle Sheets | Miracle Sheets, cooling sheets | 2+ | Cooling/luxury sheets — relay: dreamcosmos@rerreheat.com |
| HexClad | HexClad, cookware, kitchen | 1 | Hybrid cookware — relay: kitchengearupgrade@photonlush.com |
| Jacuzzi Bath Remodel | Jacuzzi, bath remodel, free fixtures | 3+ | Bathroom remodeling — relay: stylishlav@engdebatable.com |
| Exit My Timeshare | Exit My Timeshare, timeshare exit | 1 | Timeshare exit scam — relay: freesharevisionjoy@permodivide.com |
| Aptive Pest Control | Aptive, pest control, over half million | 1 | Pest control service — relay: rapidexterminators@airpowdering.com |
| Zippy Loan | Zippy Loan, $15k, Spring into | 2+ | Short-term loan service — relay: savings@afpogo.info |

---

## Unmatched Patterns (skipped, ~400+ emails)

These are real spam but don't match current patterns. Candidates for adding.

### High volume unmatched themes

| Theme | Approx count | Example subjects | Suggested keywords |
|---|---|---|---|
| Generic debt/credit | ~72 | "$20k+ in credit card debt?", "HELOC could help", "0% Intro APR until 2027", "loans in minutes" | No fixed brand — broad category spam |
| Legal/lawsuit solicitation | ~43 | "Weed killer exposure NHL/CLL?", "9/11 Victim Compensation", "Under 18 when addicted to social media?" | Roundup, NHL, CLL, 9/11, class action |
| Generic car insurance | ~25 | "Save 50% on auto insurance", "Compare free quotes", "Are you paying too much?" | Generic — no brand anchor |
| Sleep/mattress | ~20 | "Luxury Comfort, $300 off", "Upgrade To Blissy", "Saatva" | Blissy, Saatva, mattress, pillow |
| Home remodel/bathroom | ~20 | "Transform Your Bathroom", "From Ordinary to Extraordinary" | Bathroom, remodel, extraordinary |
| Chef meal delivery | ~17 | "Chef-Cooked Meals Delivered", "Dinner's Done", "Your First Box" | Chef, meal delivery, ForkFul |
| Phishing/fake alerts | ~15 | "Shipping address confirm", "Account suspended", "Data loss in progress", "🕒 Your plan has expired" | **HIGH RISK** — Shipping address, account suspended, emoji + urgency |
| AARP | ~10 | "AARP Members", "Choose Your Gift When You Join AARP" | AARP |
| Vegas/prize scams | ~10 | "Complimentary Vegas Getaway", "You've been chosen!" | Vegas getaway, you've been chosen |
| BetterHelp (standalone) | ~9 | "Licensed Online Therapy", "Transform Your Mental Health" | BetterHelp — note: also used by eharmony affiliate |
| Plasma donation | ~3 | "BioLife Plasma" | BioLife |
| Tinnitus | ~3 | "The 'Tinnitus Off Switch'" | Tinnitus |
| Google Cloud phishing | ~2 | "Your account has been locked", "Payment method invalid", "🕒 Your plan has expired" | **CRITICAL PHISHING** — Fake Google Cloud domain (info@-----mail.wN0WCBw7Ou2c.com) |

---

## Key Observations

### 1. eharmony as affiliate spam vessel
The single largest spam sender. eharmony's identity (sender name/domain) is reused by an affiliate network to deliver completely unrelated ads: window replacement, meal delivery, AARP membership, therapy, insurance. This is not eharmony spam — it's a spoofed/affiliate sending identity.

### 2. Sender obfuscation
Real company names often differ from the sending domain:
- TruGreen email appears sent from `mailtrk.com`, `signalwinter.com`, etc.
- CarShield from `fasunit.com`, `mahfridge.com`
- **New observation:** Relay domains rotate rapidly. Same brand (e.g., Blissy) uses 3+ different relay domains in a single week

### 3. Parallel campaigns
Multiple senders run the same ad simultaneously under different subjects. E.g., Roof spam had 4 different subjects all for "metal roofing" from different relay domains. Pattern matching by subject keyword (not sender domain) is more reliable.

### 4. Phishing disguised as legitimate alerts
~15 emails use urgent fake alerts: package delivery confirmations (bolded unicode text), account suspensions, data loss warnings. These are phishing, not ad spam. 

**⚠️ NEW RISK:** Google Cloud phishing with spoofed domain using unicode obfuscation:
- Fake domain: `info@-----mail.wN0WCBw7Ou2c.com`
- Subject: "🕒 Your plan has expired"
- Content: Fake payment method + account locked warnings

### 5. Seasonal patterns
- Lawn care (TruGreen) and roofing peak in spring
- Window ads constant year-round
- Canvas prints spike around Mother's Day
- Blissy/Miracle Sheets spike in spring (seasonal promotions)

### 6. High-frequency relay domains (NEW)
These domains appear across multiple unrelated spam brands:
- `savings@afpogo.info` — Destiny Mastercard, ZippyLoan, RenewalByAndersen, SBLI
- `private@micpai.com` — Ethos, Blissy, USA Wild Seafood, Liz Buys Houses
- `find@mishresilient.info` — Ethos, JacuzziBath, USA Wild Seafood

These are **super-relays** used by multiple affiliate networks. Blocking the relay domain prevents ~5-7 different brands in one go.

---

## Relay Domains (known spam senders — do NOT unsubscribe)

Seen as actual sending domains for known spam brands:
`handletitle.com`, `signalwinter.com`, `mahfridge.com`, `fasunit.com`, `mailtrk.com`, `cuonlineedu.in`, `mishresilient.info`, `afpogo.info`, `micpai.com`

**Super-relay domains (used by 5+ brands):**
- `savings@afpogo.info`
- `private@micpai.com`
- `find@mishresilient.info`

---

## Stats Snapshot (2026-05-12 → 2026-05-19, latest run)

- Processed: 653 → ~700+ emails
- Moved: 275 → ~300+ (43%)
- Skipped: 378 → ~400+ (57%)
- Estimated total in folder: ~2,600

**New patterns added (2026-05-13):**
- Destiny Mastercard (credit card)
- TRA Services (tax debt)
- Brinks Home (home security)
- Rate Equity (HELOC)
- TheCapitalWallet (loan matching)
- NorthStar-Loans (loan matching)
- UsaWildSeaFood (food delivery)
- Telstra WiFi Booster (tech/regional)

**New patterns added (2026-05-19):**
- Blissy (sheets/bedding) — high frequency
- Miracle Sheets (sheets/bedding) — emerging
- HexClad (cookware) — new
- Keranique (hair loss) — health scam
- Jacuzzi Bath Remodel (bathroom remodel) — confirmed high volume
- Exit My Timeshare (timeshare exit scam) — emerging pattern
- Aptive Pest Control (pest control)
- Zippy Loan (loan matching)
- Orangetheory Fitness (gym classes) — confirmed ~9 instances
- **Google Cloud phishing** — CRITICAL phishing alert with spoofed domain

---

## Recommendations for Next Steps

1. **Block super-relay domains** instead of individual brands — more efficient
2. **Implement subject line pattern matching** for phishing (emoji + urgency keywords)
3. **Add critical phishing alert** for Google Cloud domain variants
4. **Monitor emerging brands** (Exit My Timeshare, Aptive Pest Control)
5. **Consider time-based rules** for seasonal spam (roofing/lawn care in spring)
- subject: "Help Home Depot improve"
  category: home_services
  notes: User confirmed this is spam (disguised as feedback survey)

## New patterns (2026-06-04)
| Pattern | Count | Example subject / sender domain | Keywords |
|---------|-------|-------------------------------|----------|
| Fake Costco rewards | ~2 | "Costco Membership Benefits", "Costco Beach Reward" / `CostcoMembershipnsr.com`, `hyKmAa1Koq0j.com` | Costco, membership, rewards, gift, beach |
| Drive-Safe-Insure | ~1 | "See What You Could Find by Reviewing Your Options" / `setdroplet.xyz` | drive, safe, insure, review, options |
| Japanese music event spam | ~1 | "Lunart内海響子サポーター倶楽部" / `lunart.kyoko.utsumi@gmail.com` | 内海響子, Lunart, サポーター, 倶楽部, 終演 |
