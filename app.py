from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import csv
import os
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

def update_or_append_prelim_csv(candidate_str, judge_slot, judge_name, prod_sum, cas_sum, swim_sum, adv_sum, gown_sum, qa_sum, grand_total, timestamp):
    rows = []
    updated = False
    
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            headers = next(reader, None)
            if headers:
                rows.append(headers)
                for row in reader:
                    if len(row) >= 3 and row[0] == candidate_str and row[1] == judge_slot:
                        old_p = float(row[3]) if len(row) > 3 and float(row[3]) > 0 else 0
                        old_c = float(row[4]) if len(row) > 4 and float(row[4]) > 0 else 0
                        old_s = float(row[5]) if len(row) > 5 and float(row[5]) > 0 else 0
                        old_a = float(row[6]) if len(row) > 6 and float(row[6]) > 0 else 0
                        old_g = float(row[7]) if len(row) > 7 and float(row[7]) > 0 else 0
                        old_q = float(row[8]) if len(row) > 8 and float(row[8]) > 0 else 0

                        new_p = prod_sum if prod_sum > 0 else old_p
                        new_c = cas_sum if cas_sum > 0 else old_c
                        new_s = swim_sum if swim_sum > 0 else old_s
                        new_a = adv_sum if adv_sum > 0 else old_a
                        new_g = gown_sum if gown_sum > 0 else old_g
                        new_q = qa_sum if qa_sum > 0 else old_q

                        g_total = (new_p * 0.15) + (new_c * 0.15) + (new_s * 0.15) + (new_a * 0.20) + (new_g * 0.15) + (new_q * 0.20)

                        rows.append([
                            candidate_str, judge_slot, judge_name,
                            round(new_p, 2), round(new_c, 2), round(new_s, 2), round(new_a, 2), round(new_g, 2), round(new_q, 2),
                            round(g_total, 2), timestamp
                        ])
                        updated = True
                    else:
                        rows.append(row)

    if not updated:
        if not rows:
            init_csv()
            with open(CSV_FILE, mode='r', encoding='utf-8') as file:
                rows = list(csv.reader(file))
        rows.append([
            candidate_str, judge_slot, judge_name,
            round(prod_sum, 2), round(cas_sum, 2), round(swim_sum, 2), round(adv_sum, 2), round(gown_sum, 2), round(qa_sum, 2),
            round(grand_total, 2), timestamp
        ])

    with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerows(rows)

def update_or_append_top5_csv(candidate, judge_slot, judge_name, b_facial, b_poise, b_conf, beauty_total, br_substance, br_intelligence, br_clarity, br_delivery, brain_total, top5_total, timestamp):
    rows = []
    found = False
    if os.path.exists(TOP5_CSV_FILE):
        with open(TOP5_CSV_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header:
                rows.append(header)
            for row in reader:
                if len(row) >= 3 and row[0] == candidate and row[1] == judge_slot:
                    rows.append([
                        candidate, judge_slot, judge_name,
                        b_facial, b_poise, b_conf, round(beauty_total, 2),
                        br_substance, br_intelligence, br_clarity, br_delivery, round(brain_total, 2),
                        round(top5_total, 2), timestamp
                    ])
                    found = True
                else:
                    rows.append(row)

    if not found:
        if not rows:
            rows.append(["Candidate", "Judge ID", "Judge Name", "Beauty Facial (Max 15)", "Beauty Poise (Max 10)", "Beauty Confidence (Max 5)", "BEAUTY TOTAL (30)", "Brain Substance (Max 15)", "Brain Intelligence (Max 10)", "Brain Clarity (Max 10)", "Brain Delivery (Max 5)", "BRAIN TOTAL (40)", "TOP5 TOTAL (70)", "Timestamp"])
        rows.append([
            candidate, judge_slot, judge_name,
            b_facial, b_poise, b_conf, round(beauty_total, 2),
            br_substance, br_intelligence, br_clarity, br_delivery, round(brain_total, 2),
            round(top5_total, 2), timestamp
        ])

    with open(TOP5_CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(rows)

# --- ROUTE 2: Saving Judge Scores (Prelim or Top 5) ---
@app.route('/submit_score', methods=['POST'])
def save_score():
    init_csv()
    round_type = request.form.get('round_type', 'prelim')
    candidate = request.form.get('candidate_number', '')
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

        grand_total = prod_sum + cas_sum + swim_sum + adv_sum + gown_sum + qa_sum
        
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
    init_csv()
    
    prelim_done = {}     # step -> { candNum: true }
    top5_done = {}       # step -> { candNum: true }

    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get('Judge ID') == judge_slot:
                    cand_str = row.get('Candidate', '')
                    if cand_str:
                        cand_num = str(int(cand_str.replace('Candidate ', '')))
                        
                        p_val = float(row.get('Production (Max 100)', 0))
                        c_val = float(row.get('Casual Wear (Max 100)', 0))
                        s_val = float(row.get('Swimwear (Max 100)', 0))
                        a_val = float(row.get('Advocacy (Max 100)', 0))
                        g_val = float(row.get('Evening Gown (Max 100)', 0))
                        q_val = float(row.get('Q&A (Max 100)', 0))

                        if p_val > 0:
                            if '1' not in prelim_done: prelim_done['1'] = {}
                            prelim_done['1'][cand_num] = True

                        if c_val > 0:
                            if '2' not in prelim_done: prelim_done['2'] = {}
                            prelim_done['2'][cand_num] = True

                        if s_val > 0:
                            if '3' not in prelim_done: prelim_done['3'] = {}
                            prelim_done['3'][cand_num] = True

                        if a_val > 0:
                            if '4' not in prelim_done: prelim_done['4'] = {}
                            prelim_done['4'][cand_num] = True

                        if g_val > 0:
                            if '5' not in prelim_done: prelim_done['5'] = {}
                            prelim_done['5'][cand_num] = True

                        if q_val > 0:
                            if '6' not in prelim_done: prelim_done['6'] = {}
                            prelim_done['6'][cand_num] = True

    if os.path.exists(TOP5_CSV_FILE):
        with open(TOP5_CSV_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get('Judge ID') == judge_slot:
                    cand_str = row.get('Candidate', '')
                    if cand_str:
                        cand_num = str(int(cand_str.replace('Candidate ', '')))
                        b_tot = float(row.get('BEAUTY TOTAL (30)', 0))
                        br_tot = float(row.get('BRAIN TOTAL (40)', 0))

                        if b_tot > 0:
                            if '1' not in top5_done: top5_done['1'] = {}
                            top5_done['1'][cand_num] = True

                        if br_tot > 0:
                            if '2' not in top5_done: top5_done['2'] = {}
                            top5_done['2'][cand_num] = True

    return jsonify({
        'prelim_done': prelim_done,
        'top5_done': top5_done
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
    prelim_by_judge = {}     # cand_num -> { judge_slot: score }
    category_by_judge = {}   # cand_num -> { judge_slot: { 'prod': p, 'casual': c, ... } }
    judge_progress = {}
    
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                cand_str = row.get('Candidate', '')
                score_str = row.get('FINAL SCORE', '')
                j_slot = row.get('Judge ID', 'Unknown')
                
                if cand_str:
                    try:
                        cand_num = int(cand_str.replace('Candidate ', ''))
                        score = to_float(score_str)
                        
                        p_val = to_float(row.get('Production (Max 100)', 0))
                        c_val = to_float(row.get('Casual Wear (Max 100)', 0))
                        s_val = to_float(row.get('Swimwear (Max 100)', 0))
                        a_val = to_float(row.get('Advocacy (Max 100)', 0))
                        g_val = to_float(row.get('Evening Gown (Max 100)', 0))
                        q_val = to_float(row.get('Q&A (Max 100)', 0))

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

    # Read Top 5 Judge Scores (Per Judge Breakdown)
    top5_beauty_by_judge = {} # cand_num -> { judge_slot: b_score }
    top5_brain_by_judge = {}  # cand_num -> { judge_slot: br_score }

    if os.path.exists(TOP5_CSV_FILE):
        with open(TOP5_CSV_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                cand_str = row.get('Candidate', '')
                b_tot = row.get('BEAUTY TOTAL (30)', '')
                br_tot = row.get('BRAIN TOTAL (40)', '')
                j_slot = row.get('Judge ID', 'Unknown')

                if cand_str:
                    try:
                        cand_num = int(cand_str.replace('Candidate ', ''))
                        b_val = float(b_tot) if b_tot else 0
                        br_val = float(br_tot) if br_tot else 0

                        if b_tot:
                            if cand_num not in top5_beauty_by_judge: top5_beauty_by_judge[cand_num] = {}
                            top5_beauty_by_judge[cand_num][j_slot] = b_val
                        if br_tot:
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

        calc_prelim_total = prod_avg + casual_avg + swim_avg + adv_avg + gown_avg + qa_avg
        p_scores = list(p_dict.values())
        prelim_avg = sum(p_scores) / len(p_scores) if p_scores else calc_prelim_total
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
    scored_prelim = [c for c in candidates_data if c['submission_count'] > 0 or c['prelim_score'] > 0]
    
    # Sort by prelim_score to select the 5 official qualifiers
    prelim_sorted = sorted(candidates_data, key=lambda x: (x['prelim_score'], -x['number']), reverse=True)
    top5_qualifiers = prelim_sorted[:5]

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
        if len(scored_prelim) > 0 and has_any_top5_scores:
            cand['title'] = titles[idx]
        elif len(scored_prelim) > 0:
            cand['title'] = "Pending Top 5 Finals"
        else:
            cand['title'] = "-"

    judge_summary = {j: len(cands) for j, cands in judge_progress.items()}
    return {'candidates': candidates_data, 'top5_candidates': top5_candidates, 'judge_summary': judge_summary}

@app.route('/api/admin_data')
def admin_data():
    """Real-time JSON endpoint for live polling on Admin dashboard."""
    return jsonify(get_tabulation_data())

if __name__ == '__main__':
    init_csv()
    print("Starting Tabulation Server...")
    app.run(host='0.0.0.0', port=5000, debug=True)



