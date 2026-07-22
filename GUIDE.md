# Getting More Interviews — Playbook for Nishkarsh Jain

A practical, profile-specific guide for landing VLSI/ASIC roles in India (and remote). Pair this with the **Resume Job-Hunt Toolkit** — the strategy below tells you *what* to do; the toolkit makes each application *fast and targeted*.

**Your positioning:** Fresh graduate with internships at **Synopsys** (Zebu emulation, UART transactors), **Nvidia** (STA, timing closure), and **Jabil** (5G RF hardware test). Primary target: **Design Verification (UVM/SystemVerilog)**. Secondary: RTL, PD/STA, Emulation, Embedded, RF/DSP/SDR. BE ECE from Thapar (9.05 GPA).

---

## LinkedIn optimization

Recruiters search by keywords, not degrees. Your profile should read like the JD you want.

### Headline (120 characters — make every word count)

Pick one style and rotate monthly to A/B test:

1. **VLSI Design Verification | UVM/SystemVerilog | Constrained-Random | Emulation (Zebu) | STA**
2. **ASIC DV Engineer | SystemVerilog/UVM | Functional Coverage & SVA | C++/Python Automation | Synopsys/Nvidia**
3. **VLSI Engineer | Design Verification & Emulation | UVM | STA & Physical Design | FPGA/5G Projects**

### About section (metrics-driven template)

Use this structure — fill in your real numbers:

```
VLSI engineer (BE ECE, Thapar, 9.05 GPA) targeting Design Verification roles in India and remote.

WHAT I'VE DONE:
• Synopsys — Built UART transactors and HW/SW testbench compatibility tooling for Zebu emulation (C++).
• Nvidia — Drove timing closure on advanced SoC blocks: STA analysis, Perl automation, crosstalk/transition fixes.
• Jabil — Debugged and tested Ericsson 5G RU (AIR3268) on production test lines.

WHAT I BRING:
• Languages: SystemVerilog, Verilog, C/C++, Python, Perl
• Domains: UVM-style verification mindset, emulation, STA, FPGA (KC705/Vivado), RF/SDR (Pluto SDR)
• Tools: VCS, PrimeTime, Vivado, Simulink — plus fast scripting and documentation

OPEN TO: DV, emulation, RTL, and PD/STA roles at semiconductor and EDA companies.
Let's connect: github.com/nish-karsh
```

### Featured section

Pin 2–3 items:

- Your best **GitHub repo** (see below)
- A **project write-up** (5G modem on FPGA, Zebu/UART work if NDAs allow a sanitized description)
- **ZEBU Emulator Fundamental Training** or VLSI certification PDF

### Skills to pin (add these exact keywords)

LinkedIn allows 50 skills; pin the top 5 that match DV JDs. Add all of these to your profile:

**Core DV:** UVM, SystemVerilog, Verilog, constrained-random verification, functional coverage, assertions (SVA), scoreboard, RAL (register abstraction layer), testbench architecture, verification planning

**Supporting:** C/C++, Python, Perl, scripting/automation, VCS, simulation, gate-level simulation, waveform debug (Verdi/DVE if applicable)

**Protocols & domains:** AMBA, AXI, APB, UART, low-power (UPF), STA, static timing analysis, emulation, Zebu, FPGA, Vivado

**Soft signal:** Problem solving, technical documentation, cross-functional collaboration

Even if your internship bullets say "C++ transactor" rather than "UVM testbench," list UVM and SystemVerilog as skills and back them up in projects/coursework (VLSI Design-FPGA and ASIC cert, personal verification exercises on GitHub).

### Open to Work

- Turn on **"Open to Work"** visible to **recruiters only** (shield badge from public if you prefer discretion).
- Set job titles: Design Verification Engineer, ASIC Verification Engineer, DV Engineer, Verification Engineer, Emulation Engineer.
- Locations: India + **Remote**.
- Start date: Immediate / negotiable.

### Recommendations

Request 1–2 sentences from:

- Synopsys manager or mentor (emulation, teamwork, C++ quality)
- Nvidia intern lead (STA rigor, automation, learning speed)

Offer to draft the text for them — most managers appreciate a template.

### Weekly cadence (30–45 min/week)

| Day | Action |
|-----|--------|
| **Monday** | Comment thoughtfully on 3 posts from VLSI/DV influencers or company pages |
| **Wednesday** | Share one short post: a debugging lesson, a tool tip, or a project screenshot |
| **Friday** | Connect with 5 recruiters or hiring managers at target companies (personalized note, 2 lines max) |

Consistency beats viral posts. Recruiters notice active, technical profiles.

---

## Application funnel strategy

### Speed wins

Apply within **24–48 hours** of a posting. Early applicants get more screen time. Use the toolkit to tailor in minutes, not hours.

### Referrals first

A referral 5×'s your odds. Prioritize:

**Thapar alumni** at target companies (LinkedIn → Thapar Institute → filter by company).

**Employees at:** Qualcomm, Intel, AMD, Nvidia, Synopsys, Cadence, Micron, Texas Instruments, MediaTek, Marvell, NXP, plus Indian design centers (Wipro VLSI, HCLTech, L&T, Tessolve, Saankhya Labs, etc.).

**How to ask:** "Hi [Name], I'm a Thapar ECE '25 grad with Synopsys/Nvidia internship experience targeting DV roles. I saw [Team/Role] at [Company] — would you be open to a 10-min chat or a referral if it's a fit? Happy to share my resume."

### Channels (use all, track in spreadsheet)

| Channel | Tips |
|---------|------|
| **LinkedIn Easy Apply** | Fast but noisy — always tailor resume; use toolkit ATS check before submitting |
| **Naukri / Instahyre** | Strong for India semiconductor; paste JD into toolkit (links often block scraping) |
| **Company career portals** | Best conversion for Nvidia, Intel, AMD, Synopsys, Cadence — apply direct + find recruiter on LinkedIn |
| **Cold email** | Use toolkit **Email** button → review `.eml` → send to recruiter or hiring manager |

### GitHub hygiene

Your profile: [github.com/nish-karsh](https://github.com/nish-karsh)

Aim for 1–2 **pinned repos** that scream "verification engineer":

- A small **UVM or SystemVerilog testbench** (e.g. simple APB/UART VIP, scoreboard + coverage)
- A **Python/Perl script** that parses sim logs or STA reports (mirrors your Nvidia/Synopsys work)

README each repo with: problem, approach, how to run, screenshot of waves or coverage report. Recruiters click GitHub — make the first 10 seconds count.

### Follow-up discipline

Log every application in `data/applications.xlsx` (or **Save to tracker** in the app). Follow up at **7 days** (LinkedIn message) and **14 days** (email) if no response. Polite, one line: "Checking in on my application for [Role] — still very interested."

---

## Resume & ATS best practices (VLSI DV)

ATS systems scan for keywords and clean formatting. Your toolkit enforces one-column, parseable PDFs — but you still need the right words.

### Must-have keywords (mirror the JD)

Use naturally in summary, skills, and bullets:

| Category | Keywords |
|----------|----------|
| **Methodology** | UVM, SystemVerilog, constrained-random, directed tests, regression, verification plan, testbench, VIP |
| **Coverage & checks** | functional coverage, code coverage, assertions, SVA, scoreboard, checkers, RAL |
| **Languages** | SystemVerilog, Verilog, C, C++, Python, Perl, Tcl |
| **Tools** | VCS, Questa, Xcelium, Verdi, PrimeTime (for DV+STA crossover roles) |
| **Protocols** | AMBA, AXI, APB, AHB, PCIe, DDR, UART, SPI, I2C |
| **Advanced** | gate-level sim, low-power, UPF, emulation, FPGA prototyping, formal verification (if true) |
| **Soft** | debug, root-cause analysis, cross-team collaboration, documentation |

### Bullet formula

**Action + technical detail + outcome (metric if possible)**

- Weak: "Worked on verification."
- Strong: "Developed UART transactor for Zebu emulation platform in C++; enabled backwards-compatible HW/SW testbench migration across 3 transactor releases."

Your Synopsys/Nvidia bullets already follow this — the toolkit surfaces the best ones per JD.

### What to avoid

- Two-column or graphic-heavy layouts (ATS parsers break)
- Skills you cannot defend in an interview
- Generic summary ("hardworking team player") — replace with domain + tools + target role
- One resume for all jobs — **tailor every time** (this is what the toolkit automates)

### Role-specific emphasis

| If the JD emphasizes… | Lead with… |
|------------------------|------------|
| Pure DV / UVM | UVM keywords, testbench, coverage, SVA; coursework/projects if internship was emulation-heavy |
| Emulation | Zebu, transactors, C++, HW/SW co-verification |
| STA / PD crossover | Nvidia STA bullets, PrimeTime, timing closure, Perl automation |
| Embedded / FPGA | KC705, Vivado, 5G modem project, Pluto SDR |
| RF / hardware test | Jabil 5G RU experience, Keysight, PCBA debug |

The six cached variants in `resumes/variants/` align to these tracks for offline fallback.

---

## How this toolkit supports the strategy

| Strategy step | Toolkit feature |
|---------------|-----------------|
| **Tailor resume per job in minutes** | **Tailor** — AI reorders skills, picks bullets, rewrites summary; no-fabrication guardrail keeps you honest |
| **Close ATS keyword gaps** | **ATS** — shows missing JD terms so you can re-run tailor or edit `profile.yaml` once |
| **Apply within 24–48h** | Full pipeline (~4 API calls) completes in one session; `run.bat` → paste JD → Tailor → download PDF |
| **Personalized outreach** | **Cover letter** + **Email** — drafts aligned to company/role; you review and send (`.eml` with resume attached) |
| **Track follow-ups** | **Save to tracker** → `data/applications.xlsx` — never lose an application or miss a follow-up date |
| **JD link blocked?** | Paste text manually — still works |
| **Offline / rate limited?** | TF-IDF variant matcher picks best cached resume; retry AI tailoring when back online |
| **Consistent PDF format** | LaTeX one-column template — ATS-safe every time |

### Suggested workflow per application (~15–20 min)

1. Find a role on LinkedIn/Naukri/company portal.
2. Copy JD text → paste into app (or try link, fall back to paste).
3. Click **Tailor** → review PDF in `resumes/output/`.
4. Click **ATS** → if gaps remain, note missing keywords and re-tailor or tweak `profile.yaml` skills once.
5. Click **Cover letter** and **Email** → personalize one line in each, then send.
6. Click **Save to tracker** → apply on the portal with the tailored PDF.
7. Set a calendar reminder for 7-day follow-up.

Do this for **5–10 quality applications per week** rather than 50 generic sprays. Your profile (Synopsys + Nvidia + 9.05 GPA) is competitive — targeted volume + referrals will move the needle.

---

## Mindset

Job hunting in VLSI is a numbers game **with quality**. Rejections are normal; they usually mean "timing" or "slight skill mismatch," not "you're not good enough." Every tailored application is practice articulating your Synopsys emulation and Nvidia STA story.

Use the toolkit to remove friction so you spend energy on **networking, referrals, and interview prep** — not reformatting Word docs at midnight.

You've already done the hard part (real internships at top companies). Now make every application show that clearly.

Good luck — and update `config/profile.yaml` as you add projects, skills, or metrics. The toolkit gets better as your profile grows.
