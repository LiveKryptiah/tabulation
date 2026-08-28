from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import csv
import os
import threading
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sk_tabulation_secret_key_2026')

# Determine writable CSV location for Vercel serverless environment (/tmp) or local environment
CSV_FILE = '/tmp/pageant_scores.csv' if os.environ.get('VERCEL') else 'pageant_scores.csv'

# Default PIN for judges (Can be changed via environment variable or default)
JUDGE_PIN = os.environ.get('JUDGE_PIN', '1234')

TOP5_CSV_FILE = '/tmp/pageant_top5_scores.csv' if os.environ.get('VERCEL') else 'pageant_top5_scores.csv'

def init_csv():
    """Ensure CSV files exist with headers."""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                'Candidate', 
                'Judge ID',
                'Judge Name',
                'Production (Max 100)', 'Casual Wear (Max 100)', 'Swimwear (Max 100)', 
                'Advocacy (Max 100)', 'Evening Gown (Max 100)', 'Q&A (Max 100)', 
                'FINAL SCORE',
                'Timestamp'
            ])
            
    if not os.path.exists(TOP5_CSV_FILE):
        with open(TOP5_CSV_FILE, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                'Candidate',
                'Judge ID',
                'Judge Name',
                'Beauty Facial (Max 15)', 'Beauty Poise (Max 10)', 'Beauty Confidence (Max 5)', 'BEAUTY TOTAL (30)',
                'Brain Substance (Max 15)', 'Brain Intelligence (Max 10)', 'Brain Clarity (Max 10)', 'Brain Delivery (Max 5)', 'BRAIN TOTAL (40)',
                'TOP5 TOTAL (70)',
                'Timestamp'
            ])

# --- ROUTE 1: LOGIN FORM FIRST (Root URL) ---
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        slot = request.form.get('judge_slot', 'Judge 1')
        name = request.form.get('judge_name', '').strip()
        pin = request.form.get('pin', '').strip()

        if slot == 'Admin' or pin == 'admin':
            if pin == 'admin' or pin == JUDGE_PIN:
                session['logged_in'] = True
                session['role'] = 'admin'
                return redirect(url_for('admin_panel'))
            else:
                return render_template('login.html', error="Invalid Admin PIN! Default Admin PIN is admin.")
        elif pin == JUDGE_PIN or pin == '1234':
            session['judge_slot'] = slot
            session['judge_name'] = name if name else slot
            session['logged_in'] = True
            session['role'] = 'judge'
            return redirect(url_for('scoring'))
        else:
            return render_template('login.html', error="Invalid PIN! Default Judge PIN is 1234, Admin PIN is admin.")

    return render_template('login.html')

# --- ROUTE: LOGOUT ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ROUTE 2: The Judges' Scoring Form ---
@app.route('/scoring')
def scoring():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('index.html', 
                           judge_slot=session.get('judge_slot', 'Judge 1'), 
                           judge_name=session.get('judge_name', 'Judge'))

def to_float(val):
    try:
        return float(val) if val is not None and str(val).strip() != '' else 0.0
    except (ValueError, TypeError):
        return 0.0

# Global In-Memory Score Stores (Preserves all judges data seamlessly)
PRELIM_STORE = {}  # (cand_str, judge_slot) -> dict
TOP5_STORE = {}    # (cand_str, judge_slot) -> dict
STORE_LOCK = threading.Lock()  # Protect concurrent read/write to stores and CSV
_STORES_INITIALIZED = False  # Track whether initial CSV load has happened

def _load_prelim_from_csv():
    """Internal: Read prelim CSV rows into PRELIM_STORE (additive merge)."""
    if not os.path.exists(CSV_FILE):
        return
    try:
        with open(CSV_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader, None)
            for row in reader:
                if len(row) >= 10:
                    cand_str = row[0].strip()
                    j_slot = row[1].strip()
                    j_name = row[2].strip()
                    key = (cand_str, j_slot)

                    prod_val = to_float(row[3])
                    cas_val = to_float(row[4])
                    swim_val = to_float(row[5])
                    adv_val = to_float(row[6])
                    gown_val = to_float(row[7])
                    qa_val = to_float(row[8])
                    g_total = to_float(row[9])

                    existing = PRELIM_STORE.get(key, {})
                    new_p = prod_val if prod_val > 0 else existing.get('prod', 0)
                    new_c = cas_val if cas_val > 0 else existing.get('casual', 0)
                    new_s = swim_val if swim_val > 0 else existing.get('swim', 0)
                    new_a = adv_val if adv_val > 0 else existing.get('adv', 0)
                    new_g = gown_val if gown_val > 0 else existing.get('gown', 0)
                    new_q = qa_val if qa_val > 0 else existing.get('qa', 0)
                    calc_total = (new_p * 0.15) + (new_c * 0.15) + (new_s * 0.15) + (new_a * 0.20) + (new_g * 0.15) + (new_q * 0.20)
                    final_total = g_total if g_total > 0 else calc_total

                    PRELIM_STORE[key] = {
                        'candidate_str': cand_str,
                        'judge_slot': j_slot,
                        'judge_name': j_name,
                        'prod': round(new_p, 2),
                        'casual': round(new_c, 2),
                        'swim': round(new_s, 2),
                        'adv': round(new_a, 2),
                        'gown': round(new_g, 2),
                        'qa': round(new_q, 2),
                        'grand_total': round(final_total, 2),
                        'timestamp': row[10] if len(row) > 10 else ''
                    }
    except Exception as e:
        print("Error reading prelim CSV to store:", e)


def _load_top5_from_csv():
    """Internal: Read top5 CSV rows into TOP5_STORE (additive merge)."""
    if not os.path.exists(TOP5_CSV_FILE):
        return
    try:
        with open(TOP5_CSV_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader, None)
            for row in reader:
                if len(row) >= 13:
                    cand_str = row[0].strip()
                    j_slot = row[1].strip()
                    j_name = row[2].strip()
                    key = (cand_str, j_slot)

                    b_fac = to_float(row[3])
                    b_poi = to_float(row[4])
                    b_cnf = to_float(row[5])
                    b_tot = to_float(row[6])
                    br_sub = to_float(row[7])
                    br_int = to_float(row[8])
                    br_cla = to_float(row[9])
                    br_del = to_float(row[10])
                    br_tot = to_float(row[11])
                    t5_tot = to_float(row[12])

                    existing = TOP5_STORE.get(key, {})
                    new_b_fac = b_fac if b_fac > 0 else existing.get('b_facial', 0)
                    new_b_poi = b_poi if b_poi > 0 else existing.get('b_poise', 0)
                    new_b_cnf = b_cnf if b_cnf > 0 else existing.get('b_conf', 0)
                    calc_b = new_b_fac + new_b_poi + new_b_cnf
                    new_b_tot = calc_b if calc_b > 0 else (b_tot if b_tot > 0 else existing.get('beauty_total', 0))

                    new_br_sub = br_sub if br_sub > 0 else existing.get('br_substance', 0)
                    new_br_int = br_int if br_int > 0 else existing.get('br_intelligence', 0)
                    new_br_cla = br_cla if br_cla > 0 else existing.get('br_clarity', 0)
                    new_br_del = br_del if br_del > 0 else existing.get('br_delivery', 0)
                    calc_br = new_br_sub + new_br_int + new_br_cla + new_br_del
                    new_br_tot = calc_br if calc_br > 0 else (br_tot if br_tot > 0 else existing.get('brain_total', 0))

                    final_t5 = new_b_tot + new_br_tot

                    TOP5_STORE[key] = {
                        'candidate': cand_str,
                        'judge_slot': j_slot,
                        'judge_name': j_name,
                        'b_facial': round(new_b_fac, 2),
                        'b_poise': round(new_b_poi, 2),
                        'b_conf': round(new_b_cnf, 2),
                        'beauty_total': round(new_b_tot, 2),
                        'br_substance': round(new_br_sub, 2),
                        'br_intelligence': round(new_br_int, 2),
                        'br_clarity': round(new_br_cla, 2),
                        'br_delivery': round(new_br_del, 2),
                        'brain_total': round(new_br_tot, 2),
                        'top5_total': round(final_t5, 2),
                        'timestamp': row[13] if len(row) > 13 else ''
                    }
    except Exception as e:
        print("Error reading top5 CSV to store:", e)


def ensure_stores_loaded():
    """Ensure in-memory stores are loaded from CSV."""
    sync_stores_from_csv()


def sync_stores_from_csv():
    """Ensure stores are populated and fully merged from CSV files on disk."""
    with STORE_LOCK:
        _load_prelim_from_csv()
        _load_top5_from_csv()

def update_or_append_prelim_csv(candidate_str, judge_slot, judge_name, prod_sum, cas_sum, swim_sum, adv_sum, gown_sum, qa_sum, grand_total, timestamp):
    ensure_stores_loaded()
    with STORE_LOCK:
        key = (candidate_str.strip(), judge_slot.strip())
        existing = PRELIM_STORE.get(key, {})

        old_p = existing.get('prod', 0)
        old_c = existing.get('casual', 0)
        old_s = existing.get('swim', 0)
        old_a = existing.get('adv', 0)
        old_g = existing.get('gown', 0)
        old_q = existing.get('qa', 0)

        new_p = prod_sum if prod_sum > 0 else old_p
        new_c = cas_sum if cas_sum > 0 else old_c
        new_s = swim_sum if swim_sum > 0 else old_s
        new_a = adv_sum if adv_sum > 0 else old_a
        new_g = gown_sum if gown_sum > 0 else old_g
        new_q = qa_sum if qa_sum > 0 else old_q

        g_total = (new_p * 0.15) + (new_c * 0.15) + (new_s * 0.15) + (new_a * 0.20) + (new_g * 0.15) + (new_q * 0.20)

        PRELIM_STORE[key] = {
            'candidate_str': candidate_str,
            'judge_slot': judge_slot,
            'judge_name': judge_name,
            'prod': round(new_p, 2),
            'casual': round(new_c, 2),
            'swim': round(new_s, 2),
            'adv': round(new_a, 2),
            'gown': round(new_g, 2),
            'qa': round(new_q, 2),
            'grand_total': round(g_total, 2),
            'timestamp': timestamp
        }

        _flush_prelim_csv()

def _atomic_write_csv(filepath, rows):
    """Write rows to a temp file first, then atomically replace target filepath."""
    temp_filepath = filepath + '.tmp'
    try:
        with open(temp_filepath, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        os.replace(temp_filepath, filepath)
    except Exception as e:
        print(f"Error atomic writing CSV {filepath}:", e)


def _flush_prelim_csv():
    """Write the entire PRELIM_STORE to CSV atomically. Must be called while holding STORE_LOCK."""
    rows = [[
        'Candidate', 'Judge ID', 'Judge Name',
        'Production (Max 100)', 'Casual Wear (Max 100)', 'Swimwear (Max 100)',
        'Advocacy (Max 100)', 'Evening Gown (Max 100)', 'Q&A (Max 100)',
        'FINAL SCORE', 'Timestamp'
    ]]
    for item in PRELIM_STORE.values():
        rows.append([
            item['candidate_str'], item['judge_slot'], item['judge_name'],
            item['prod'], item['casual'], item['swim'],
            item['adv'], item['gown'], item['qa'],
            item['grand_total'], item['timestamp']
        ])
    _atomic_write_csv(CSV_FILE, rows)


def _flush_top5_csv():
    """Write the entire TOP5_STORE to CSV atomically. Must be called while holding STORE_LOCK."""
    rows = [[
        'Candidate', 'Judge ID', 'Judge Name',
        'Beauty Facial (Max 15)', 'Beauty Poise (Max 10)', 'Beauty Confidence (Max 5)', 'BEAUTY TOTAL (30)',
        'Brain Substance (Max 15)', 'Brain Intelligence (Max 10)', 'Brain Clarity (Max 10)', 'Brain Delivery (Max 5)', 'BRAIN TOTAL (40)',
        'TOP5 TOTAL (70)', 'Timestamp'
    ]]
    for item in TOP5_STORE.values():
        rows.append([
            item['candidate'], item['judge_slot'], item['judge_name'],
            item['b_facial'], item['b_poise'], item['b_conf'], item['beauty_total'],
            item['br_substance'], item['br_intelligence'], item['br_clarity'], item['br_delivery'], item['brain_total'],
            item['top5_total'], item['timestamp']
        ])
    _atomic_write_csv(TOP5_CSV_FILE, rows)


def update_or_append_top5_csv(candidate, judge_slot, judge_name, b_facial, b_poise, b_conf, beauty_total, br_substance, br_intelligence, br_clarity, br_delivery, brain_total, top5_total, timestamp):
    ensure_stores_loaded()
    with STORE_LOCK:
        key = (candidate.strip(), judge_slot.strip())
        existing = TOP5_STORE.get(key, {})

        old_b_fac = existing.get('b_facial', 0)
        old_b_poi = existing.get('b_poise', 0)
        old_b_cnf = existing.get('b_conf', 0)
        old_b_tot = existing.get('beauty_total', 0)

        old_br_sub = existing.get('br_substance', 0)
        old_br_int = existing.get('br_intelligence', 0)
        old_br_cla = existing.get('br_clarity', 0)
        old_br_del = existing.get('br_delivery', 0)
        old_br_tot = existing.get('brain_total', 0)

        new_b_fac = b_facial if b_facial > 0 else old_b_fac
        new_b_poi = b_poise if b_poise > 0 else old_b_poi
        new_b_cnf = b_conf if b_conf > 0 else old_b_cnf
        calc_b_tot = new_b_fac + new_b_poi + new_b_cnf
        new_b_tot = calc_b_tot if calc_b_tot > 0 else (beauty_total if beauty_total > 0 else old_b_tot)

        new_br_sub = br_substance if br_substance > 0 else old_br_sub
        new_br_int = br_intelligence if br_intelligence > 0 else old_br_int
        new_br_cla = br_clarity if br_clarity > 0 else old_br_cla
        new_br_del = br_delivery if br_delivery > 0 else old_br_del
        calc_br_tot = new_br_sub + new_br_int + new_br_cla + new_br_del
        new_br_tot = calc_br_tot if calc_br_tot > 0 else (brain_total if brain_total > 0 else old_br_tot)

        final_t5 = new_b_tot + new_br_tot

        TOP5_STORE[key] = {
            'candidate': candidate,
            'judge_slot': judge_slot,
            'judge_name': judge_name,
            'b_facial': round(new_b_fac, 2),
            'b_poise': round(new_b_poi, 2),
            'b_conf': round(new_b_cnf, 2),
            'beauty_total': round(new_b_tot, 2),
            'br_substance': round(new_br_sub, 2),
            'br_intelligence': round(new_br_int, 2),
            'br_clarity': round(new_br_cla, 2),
            'br_delivery': round(new_br_del, 2),
            'brain_total': round(new_br_tot, 2),
            'top5_total': round(final_t5, 2),
            'timestamp': timestamp
        }

        _flush_top5_csv()

# --- ROUTE 2: Saving Judge Scores (Prelim or Top 5) ---
@app.route('/submit_score', methods=['POST'])
def save_score():
    init_csv()
    round_type = request.form.get('round_type', 'prelim')
    candidate = request.form.get('candidate_number', '')
    # IMPORTANT: Use form judge_slot as PRIMARY source.
    # The JS page bakes the correct judge_slot at render time into currentJudgeSlot.
    # Session can change if user logs in as a different judge in another tab,
    # so session must NOT override the form value from the original page.
    judge_slot = request.form.get('judge_slot') or session.get('judge_slot') or 'Judge 1'
    judge_name = request.form.get('judge_name') or session.get('judge_name') or judge_slot
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if round_type == 'top5':
        b_facial = to_float(request.form.get('b_facial'))
        b_poise  = to_float(request.form.get('b_poise'))
        b_conf   = to_float(request.form.get('b_conf'))
        beauty_total = b_facial + b_poise + b_conf

        br_substance    = to_float(request.form.get('br_substance'))
        br_intelligence = to_float(request.form.get('br_intelligence'))
        br_clarity      = to_float(request.form.get('br_clarity'))
        br_delivery     = to_float(request.form.get('br_delivery'))
        brain_total = br_substance + br_intelligence + br_clarity + br_delivery

        top5_total = beauty_total + brain_total

        update_or_append_top5_csv(
            "Candidate " + str(candidate),
            judge_slot, judge_name,
            b_facial, b_poise, b_conf, beauty_total,
            br_substance, br_intelligence, br_clarity, br_delivery, brain_total,
            top5_total, timestamp
        )
        return "Top 5 Score submitted successfully!"

    else:
        prod_sum = to_float(request.form.get('p_presence')) + to_float(request.form.get('p_execution')) + to_float(request.form.get('p_energy')) + to_float(request.form.get('p_personality'))
        cas_sum = to_float(request.form.get('c_poise')) + to_float(request.form.get('c_carriage')) + to_float(request.form.get('c_presence')) + to_float(request.form.get('c_impact'))
        swim_sum = to_float(request.form.get('s_confidence')) + to_float(request.form.get('s_carriage')) + to_float(request.form.get('s_presence')) + to_float(request.form.get('s_impact'))
        adv_sum = to_float(request.form.get('a_relevance')) + to_float(request.form.get('a_content')) + to_float(request.form.get('a_feasibility')) + to_float(request.form.get('a_communication')) + to_float(request.form.get('a_sincerity'))
        gown_sum = to_float(request.form.get('e_elegance')) + to_float(request.form.get('e_carriage')) + to_float(request.form.get('e_grace')) + to_float(request.form.get('e_styling')) + to_float(request.form.get('e_impact'))
        qa_sum = to_float(request.form.get('q_relevance')) + to_float(request.form.get('q_clarity')) + to_float(request.form.get('q_insight')) + to_float(request.form.get('q_communication')) + to_float(request.form.get('q_composure'))

        grand_total = (prod_sum * 0.15) + (cas_sum * 0.15) + (swim_sum * 0.15) + (adv_sum * 0.20) + (gown_sum * 0.15) + (qa_sum * 0.20)
        
        update_or_append_prelim_csv(
            "Candidate " + str(candidate), 
            judge_slot, judge_name,
            prod_sum, cas_sum, swim_sum, adv_sum, gown_sum, qa_sum, 
            grand_total, timestamp
        )
        return "Preliminary score submitted successfully!"

# --- ROUTE: FETCH CURRENT JUDGE'S SCORES FOR AUTOMATIC RESTORATION ON RELOAD ---
@app.route('/api/my_judge_scores')
def get_my_judge_scores():
    judge_slot = request.args.get('judge_slot') or session.get('judge_slot') or 'Judge 1'
    sync_stores_from_csv()
    
    prelim_done = {}     # step -> { candNum: true }
    top5_done = {}       # step -> { candNum: true }
    prelim_scores = {}   # candNum -> item
    top5_scores = {}     # candNum -> item

    for (cand_str, j_slot), item in PRELIM_STORE.items():
        if j_slot.strip() == judge_slot.strip():
            try:
                cand_num = str(int(cand_str.replace('Candidate ', '')))
                prelim_scores[cand_num] = item
                if item.get('prod', 0) > 0:
                    if '1' not in prelim_done: prelim_done['1'] = {}
                    prelim_done['1'][cand_num] = True
                if item.get('casual', 0) > 0:
                    if '2' not in prelim_done: prelim_done['2'] = {}
                    prelim_done['2'][cand_num] = True
                if item.get('swim', 0) > 0:
                    if '3' not in prelim_done: prelim_done['3'] = {}
                    prelim_done['3'][cand_num] = True
                if item.get('adv', 0) > 0:
                    if '4' not in prelim_done: prelim_done['4'] = {}
                    prelim_done['4'][cand_num] = True
                if item.get('gown', 0) > 0:
                    if '5' not in prelim_done: prelim_done['5'] = {}
                    prelim_done['5'][cand_num] = True
                if item.get('qa', 0) > 0:
                    if '6' not in prelim_done: prelim_done['6'] = {}
                    prelim_done['6'][cand_num] = True
            except ValueError:
                pass

    for (cand_str, j_slot), item in TOP5_STORE.items():
        if j_slot.strip() == judge_slot.strip():
            try:
                cand_num = str(int(cand_str.replace('Candidate ', '')))
                top5_scores[cand_num] = item
                if item.get('beauty_total', 0) > 0:
                    if '1' not in top5_done: top5_done['1'] = {}
                    top5_done['1'][cand_num] = True
                if item.get('brain_total', 0) > 0:
                    if '2' not in top5_done: top5_done['2'] = {}
                    top5_done['2'][cand_num] = True
            except ValueError:
                pass

    return jsonify({
        'prelim_done': prelim_done,
        'top5_done': top5_done,
        'prelim_scores': prelim_scores,
        'top5_scores': top5_scores
    })

# --- ROUTE 3: The Live Leaderboard ---
@app.route('/rankings')
def rankings():
    results = {}
    init_csv()
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                cand = row.get('Candidate')
                score_val = row.get('FINAL SCORE')
                if cand and score_val:
                    try:
                        score = float(score_val)
                        if cand not in results:
                            results[cand] = []
                        results[cand].append(score)
                    except ValueError:
                        pass
    
    leaderboard = []
    for candidate, scores in results.items():
        avg_score = sum(scores) / len(scores) if scores else 0
        leaderboard.append({'candidate': candidate, 'score': round(avg_score, 2)})
        
    leaderboard.sort(key=lambda x: x['score'], reverse=True)
    return render_template('rankings.html', leaderboard=leaderboard)

# --- ROUTE 4: READ-ONLY ADMIN TABULATION ---
@app.route('/admin')
def admin_panel():
    init_csv()
    data = get_tabulation_data()
    return render_template('admin.html', 
                           candidates=data['candidates'], 
                           top5_candidates=data['top5_candidates'], 
                           judge_summary=data['judge_summary'])

# --- HELPER & API FOR REAL-TIME TABULATION ---
def get_tabulation_data():
    sync_stores_from_csv()

    prelim_by_judge = {}     # cand_num -> { judge_slot: score }
    category_by_judge = {}   # cand_num -> { judge_slot: { 'prod': p, 'casual': c, ... } }
    judge_progress = {}

    for (cand_str, j_slot), item in PRELIM_STORE.items():
        try:
            cand_num = int(cand_str.replace('Candidate ', ''))
            score = item['grand_total']
            p_val = item['prod']
            c_val = item['casual']
            s_val = item['swim']
            a_val = item['adv']
            g_val = item['gown']
            q_val = item['qa']

            calc_score = (p_val * 0.15) + (c_val * 0.15) + (s_val * 0.15) + (a_val * 0.20) + (g_val * 0.15) + (q_val * 0.20)
            final_prelim_val = score if score > 0 else calc_score

            if cand_num not in prelim_by_judge:
                prelim_by_judge[cand_num] = {}
            if final_prelim_val > 0:
                prelim_by_judge[cand_num][j_slot] = final_prelim_val

            if cand_num not in category_by_judge:
                category_by_judge[cand_num] = {}
            if j_slot not in category_by_judge[cand_num]:
                category_by_judge[cand_num][j_slot] = {}

            if p_val > 0: category_by_judge[cand_num][j_slot]['prod'] = p_val
            if c_val > 0: category_by_judge[cand_num][j_slot]['casual'] = c_val
            if s_val > 0: category_by_judge[cand_num][j_slot]['swim'] = s_val
            if a_val > 0: category_by_judge[cand_num][j_slot]['adv'] = a_val
            if g_val > 0: category_by_judge[cand_num][j_slot]['gown'] = g_val
            if q_val > 0: category_by_judge[cand_num][j_slot]['qa'] = q_val

            if j_slot not in judge_progress:
                judge_progress[j_slot] = set()
            judge_progress[j_slot].add(cand_num)
        except ValueError:
            pass

    # Read Top 5 Judge Scores from TOP5_STORE
    top5_beauty_by_judge = {} # cand_num -> { judge_slot: b_score }
    top5_brain_by_judge = {}  # cand_num -> { judge_slot: br_score }

    for (cand_str, j_slot), item in TOP5_STORE.items():
        try:
            cand_num = int(cand_str.replace('Candidate ', ''))
            b_val = item['beauty_total']
            br_val = item['brain_total']

            if b_val > 0:
                if cand_num not in top5_beauty_by_judge: top5_beauty_by_judge[cand_num] = {}
                top5_beauty_by_judge[cand_num][j_slot] = b_val
            if br_val > 0:
                if cand_num not in top5_brain_by_judge: top5_brain_by_judge[cand_num] = {}
                top5_brain_by_judge[cand_num][j_slot] = br_val

            if j_slot not in judge_progress:
                judge_progress[j_slot] = set()
            judge_progress[j_slot].add(cand_num)
        except ValueError:
            pass

    candidates_data = []
    all_cand_nums = set(range(1, 13)).union(prelim_by_judge.keys()).union(top5_beauty_by_judge.keys())

    for cand_num in sorted(all_cand_nums):
        p_dict = prelim_by_judge.get(cand_num, {})
        b_dict = top5_beauty_by_judge.get(cand_num, {})
        br_dict = top5_brain_by_judge.get(cand_num, {})
        cand_cats = category_by_judge.get(cand_num, {})

        # Compute accurate category averages per candidate across judges
        prod_scores = [j['prod'] for j in cand_cats.values() if 'prod' in j]
        casual_scores = [j['casual'] for j in cand_cats.values() if 'casual' in j]
        swim_scores = [j['swim'] for j in cand_cats.values() if 'swim' in j]
        adv_scores = [j['adv'] for j in cand_cats.values() if 'adv' in j]
        gown_scores = [j['gown'] for j in cand_cats.values() if 'gown' in j]
        qa_scores = [j['qa'] for j in cand_cats.values() if 'qa' in j]

        prod_avg = sum(prod_scores) / len(prod_scores) if prod_scores else 0.0
        casual_avg = sum(casual_scores) / len(casual_scores) if casual_scores else 0.0
        swim_avg = sum(swim_scores) / len(swim_scores) if swim_scores else 0.0
        adv_avg = sum(adv_scores) / len(adv_scores) if adv_scores else 0.0
        gown_avg = sum(gown_scores) / len(gown_scores) if gown_scores else 0.0
        qa_avg = sum(qa_scores) / len(qa_scores) if qa_scores else 0.0

        p_scores = list(p_dict.values())
        prelim_avg = sum(p_scores) / len(p_scores) if p_scores else 0.0
        prelim_30 = prelim_avg * 0.30

        b_scores = list(b_dict.values())
        beauty_30 = sum(b_scores) / len(b_scores) if b_scores else 0.0

        br_scores = list(br_dict.values())
        brain_40  = sum(br_scores) / len(br_scores) if br_scores else 0.0

        final_score = prelim_30 + beauty_30 + brain_40

        j_breakdown = {}
        for j_id in ['Judge 1', 'Judge 2', 'Judge 3', 'Judge 4', 'Judge 5']:
            has_b = j_id in b_dict
            has_br = j_id in br_dict
            if has_b or has_br:
                tot = b_dict.get(j_id, 0) + br_dict.get(j_id, 0)
                j_breakdown[j_id] = round(tot, 2)
            else:
                j_breakdown[j_id] = '-'

        prod_j = {j_id: round(cand_cats[j_id]['prod'], 2) if (j_id in cand_cats and 'prod' in cand_cats[j_id]) else '-' for j_id in ['Judge 1', 'Judge 2', 'Judge 3', 'Judge 4', 'Judge 5']}
        casual_j = {j_id: round(cand_cats[j_id]['casual'], 2) if (j_id in cand_cats and 'casual' in cand_cats[j_id]) else '-' for j_id in ['Judge 1', 'Judge 2', 'Judge 3', 'Judge 4', 'Judge 5']}
        swim_j = {j_id: round(cand_cats[j_id]['swim'], 2) if (j_id in cand_cats and 'swim' in cand_cats[j_id]) else '-' for j_id in ['Judge 1', 'Judge 2', 'Judge 3', 'Judge 4', 'Judge 5']}
        adv_j = {j_id: round(cand_cats[j_id]['adv'], 2) if (j_id in cand_cats and 'adv' in cand_cats[j_id]) else '-' for j_id in ['Judge 1', 'Judge 2', 'Judge 3', 'Judge 4', 'Judge 5']}
        gown_j = {j_id: round(cand_cats[j_id]['gown'], 2) if (j_id in cand_cats and 'gown' in cand_cats[j_id]) else '-' for j_id in ['Judge 1', 'Judge 2', 'Judge 3', 'Judge 4', 'Judge 5']}
        qa_j = {j_id: round(cand_cats[j_id]['qa'], 2) if (j_id in cand_cats and 'qa' in cand_cats[j_id]) else '-' for j_id in ['Judge 1', 'Judge 2', 'Judge 3', 'Judge 4', 'Judge 5']}

        candidates_data.append({
            'number': cand_num,
            'name': f"Candidate {cand_num}",
            'prelim_score': round(prelim_avg, 2),
            'prelim_30': round(prelim_30, 2),
            'beauty_30': round(beauty_30, 2),
            'brain_40': round(brain_40, 2),
            'final_score': round(final_score, 2),
            'judge_1': j_breakdown.get('Judge 1', '-'),
            'judge_2': j_breakdown.get('Judge 2', '-'),
            'judge_3': j_breakdown.get('Judge 3', '-'),
            'judge_4': j_breakdown.get('Judge 4', '-'),
            'judge_5': j_breakdown.get('Judge 5', '-'),
            'prod_avg': round(prod_avg, 2),
            'casual_avg': round(casual_avg, 2),
            'swim_avg': round(swim_avg, 2),
            'adv_avg': round(adv_avg, 2),
            'gown_avg': round(gown_avg, 2),
            'qa_avg': round(qa_avg, 2),
            'prod_weighted': round(prod_avg * 0.15, 2),
            'casual_weighted': round(casual_avg * 0.15, 2),
            'swim_weighted': round(swim_avg * 0.15, 2),
            'adv_weighted': round(adv_avg * 0.20, 2),
            'gown_weighted': round(gown_avg * 0.15, 2),
            'qa_weighted': round(qa_avg * 0.20, 2),
            'prod_j': prod_j,
            'casual_j': casual_j,
            'swim_j': swim_j,
            'adv_j': adv_j,
            'gown_j': gown_j,
            'qa_j': qa_j,
            'has_top5_scores': len(b_scores) > 0 or len(br_scores) > 0,
            'submission_count': len(p_scores)
        })

    # Compute Top 5 Finalists & Titles based on real judge submissions
    has_any_prelim = any(c['prelim_score'] > 0 for c in candidates_data)

    if has_any_prelim:
        prelim_sorted = sorted(candidates_data, key=lambda x: (x['prelim_score'], -x['number']), reverse=True)
        top5_qualifiers = [c for c in prelim_sorted if c['prelim_score'] > 0][:5]
        has_any_top5_scores = any(c['has_top5_scores'] for c in top5_qualifiers)

        if has_any_top5_scores:
            top5_candidates = sorted(top5_qualifiers, key=lambda x: (x['final_score'], x['prelim_score']), reverse=True)
        else:
            top5_candidates = top5_qualifiers

        titles = [
            "👑 MISS SK YOUTH AMBASSADRESS 2026",
            "👑 1st Runner-Up",
            "👑 2nd Runner-Up",
            "👑 3rd Runner-Up",
            "👑 4th Runner-Up"
        ]

        for idx, cand in enumerate(top5_candidates):
            cand['top5_rank'] = idx + 1
            if has_any_top5_scores:
                cand['title'] = titles[idx] if idx < len(titles) else f"{idx+1}th Runner-Up"
            else:
                cand['title'] = "QUALIFIED FINALIST"
    else:
        top5_candidates = []

    judge_summary = {j: len(cands) for j, cands in judge_progress.items()}
    return {'candidates': candidates_data, 'top5_candidates': top5_candidates, 'judge_summary': judge_summary}

@app.route('/api/admin_data')
def admin_data():
    """Real-time JSON endpoint for live polling on Admin dashboard."""
    return jsonify(get_tabulation_data())

if __name__ == '__main__':
    init_csv()
    ensure_stores_loaded()
    print("Starting Tabulation Server...")
    print(f"  Prelim entries: {len(PRELIM_STORE)}, Top5 entries: {len(TOP5_STORE)}")
    app.run(host='0.0.0.0', port=5000, debug=True)



