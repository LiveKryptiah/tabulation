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

# --- ROUTE 2: Saving Judge Scores (Prelim or Top 5) ---
@app.route('/submit_score', methods=['POST'])
def save_score():
    init_csv()
    round_type = request.form.get('round_type', 'prelim')
    candidate = request.form.get('candidate_number', '')
    judge_slot = session.get('judge_slot', request.form.get('judge_slot', 'Judge 1'))
    judge_name = session.get('judge_name', request.form.get('judge_name', judge_slot))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if round_type == 'top5':
        # TOP 5 FINALS SCORING BY JUDGES
        b_facial = float(request.form.get('b_facial', 0))
        b_poise  = float(request.form.get('b_poise', 0))
        b_conf   = float(request.form.get('b_conf', 0))
        beauty_total = b_facial + b_poise + b_conf

        br_substance    = float(request.form.get('br_substance', 0))
        br_intelligence = float(request.form.get('br_intelligence', 0))
        br_clarity      = float(request.form.get('br_clarity', 0))
        br_delivery     = float(request.form.get('br_delivery', 0))
        brain_total = br_substance + br_intelligence + br_clarity + br_delivery

        top5_total = beauty_total + brain_total

        with open(TOP5_CSV_FILE, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                "Candidate " + str(candidate),
                judge_slot,
                judge_name,
                b_facial, b_poise, b_conf, round(beauty_total, 2),
                br_substance, br_intelligence, br_clarity, br_delivery, round(brain_total, 2),
                round(top5_total, 2),
                timestamp
            ])
        return "Top 5 Score submitted successfully!"

    else:
        # PRELIMINARY SCORING BY JUDGES
        prod_sum = int(request.form.get('p_presence', 0)) + int(request.form.get('p_execution', 0)) + int(request.form.get('p_energy', 0)) + int(request.form.get('p_personality', 0))
        prod_weighted = prod_sum * 0.15

        cas_sum = int(request.form.get('c_poise', 0)) + int(request.form.get('c_carriage', 0)) + int(request.form.get('c_presence', 0)) + int(request.form.get('c_impact', 0))
        cas_weighted = cas_sum * 0.15

        swim_sum = int(request.form.get('s_confidence', 0)) + int(request.form.get('s_carriage', 0)) + int(request.form.get('s_presence', 0)) + int(request.form.get('s_impact', 0))
        swim_weighted = swim_sum * 0.15

        adv_sum = int(request.form.get('a_relevance', 0)) + int(request.form.get('a_content', 0)) + int(request.form.get('a_feasibility', 0)) + int(request.form.get('a_communication', 0)) + int(request.form.get('a_sincerity', 0))
        adv_weighted = adv_sum * 0.20

        gown_sum = int(request.form.get('e_elegance', 0)) + int(request.form.get('e_carriage', 0)) + int(request.form.get('e_grace', 0)) + int(request.form.get('e_styling', 0)) + int(request.form.get('e_impact', 0))
        gown_weighted = gown_sum * 0.15

        qa_sum = int(request.form.get('q_relevance', 0)) + int(request.form.get('q_clarity', 0)) + int(request.form.get('q_insight', 0)) + int(request.form.get('q_communication', 0)) + int(request.form.get('q_composure', 0))
        qa_weighted = qa_sum * 0.20

        grand_total = prod_weighted + cas_weighted + swim_weighted + adv_weighted + gown_weighted + qa_weighted
        
        with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                "Candidate " + str(candidate), 
                judge_slot,
                judge_name,
                prod_sum, cas_sum, swim_sum, adv_sum, gown_sum, qa_sum, 
                round(grand_total, 2),
                timestamp
            ])
        return "Preliminary score submitted successfully!"

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
    prelim_results = {}
    category_results = {}
    judge_progress = {}
    
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                cand_str = row.get('Candidate', '')
                score_str = row.get('FINAL SCORE', '')
                j_slot = row.get('Judge ID', 'Unknown')
                
                if cand_str and score_str:
                    try:
                        cand_num = int(cand_str.replace('Candidate ', ''))
                        score = float(score_str)
                        if cand_num not in prelim_results:
                            prelim_results[cand_num] = []
                        prelim_results[cand_num].append(score)
                        
                        if cand_num not in category_results:
                            category_results[cand_num] = {'prod': [], 'casual': [], 'swim': [], 'adv': [], 'gown': [], 'qa': []}

                        p_val = float(row.get('Production (Max 100)', 0))
                        c_val = float(row.get('Casual Wear (Max 100)', 0))
                        s_val = float(row.get('Swimwear (Max 100)', 0))
                        a_val = float(row.get('Advocacy (Max 100)', 0))
                        g_val = float(row.get('Evening Gown (Max 100)', 0))
                        q_val = float(row.get('Q&A (Max 100)', 0))

                        category_results[cand_num]['prod'].append(p_val)
                        category_results[cand_num]['casual'].append(c_val)
                        category_results[cand_num]['swim'].append(s_val)
                        category_results[cand_num]['adv'].append(a_val)
                        category_results[cand_num]['gown'].append(g_val)
                        category_results[cand_num]['qa'].append(q_val)
                        
                        if j_slot not in judge_progress:
                            judge_progress[j_slot] = set()
                        judge_progress[j_slot].add(cand_num)
                    except ValueError:
                        pass

    # Read Top 5 Judge Scores (Per Judge Breakdown)
    top5_beauty_results = {}
    top5_brain_results = {}
    top5_judge_scores = {} # cand_num -> { judge_slot: score }

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
                            if cand_num not in top5_beauty_results: top5_beauty_results[cand_num] = []
                            top5_beauty_results[cand_num].append(b_val)
                        if br_tot:
                            if cand_num not in top5_brain_results: top5_brain_results[cand_num] = []
                            top5_brain_results[cand_num].append(br_val)

                        if cand_num not in top5_judge_scores: top5_judge_scores[cand_num] = {}
                        top5_judge_scores[cand_num][j_slot] = round(b_val + br_val, 2)

                        if j_slot not in judge_progress:
                            judge_progress[j_slot] = set()
                        judge_progress[j_slot].add(cand_num)
                    except ValueError:
                        pass

    candidates_data = []
    all_cand_nums = set(range(1, 13)).union(prelim_results.keys()).union(top5_beauty_results.keys())

    for cand_num in sorted(all_cand_nums):
        p_scores = prelim_results.get(cand_num, [])
        b_scores = top5_beauty_results.get(cand_num, [])
        br_scores = top5_brain_results.get(cand_num, [])
        cats = category_results.get(cand_num, {'prod': [], 'casual': [], 'swim': [], 'adv': [], 'gown': [], 'qa': []})

        prelim_avg = sum(p_scores) / len(p_scores) if p_scores else 0
        prelim_30 = prelim_avg * 0.30

        beauty_30 = sum(b_scores) / len(b_scores) if b_scores else 0
        brain_40  = sum(br_scores) / len(br_scores) if br_scores else 0

        final_score = prelim_30 + beauty_30 + brain_40

        j_scores = top5_judge_scores.get(cand_num, {})

        candidates_data.append({
            'number': cand_num,
            'name': f"Candidate {cand_num}",
            'prelim_score': round(prelim_avg, 2),
            'prelim_30': round(prelim_30, 2),
            'beauty_30': round(beauty_30, 2),
            'brain_40': round(brain_40, 2),
            'final_score': round(final_score, 2),
            'judge_1': j_scores.get('Judge 1', '-'),
            'judge_2': j_scores.get('Judge 2', '-'),
            'judge_3': j_scores.get('Judge 3', '-'),
            'judge_4': j_scores.get('Judge 4', '-'),
            'judge_5': j_scores.get('Judge 5', '-'),
            'prod_avg': round(sum(cats['prod']) / len(cats['prod']), 2) if cats['prod'] else 0,
            'casual_avg': round(sum(cats['casual']) / len(cats['casual']), 2) if cats['casual'] else 0,
            'swim_avg': round(sum(cats['swim']) / len(cats['swim']), 2) if cats['swim'] else 0,
            'adv_avg': round(sum(cats['adv']) / len(cats['adv']), 2) if cats['adv'] else 0,
            'gown_avg': round(sum(cats['gown']) / len(cats['gown']), 2) if cats['gown'] else 0,
            'qa_avg': round(sum(cats['qa']) / len(cats['qa']), 2) if cats['qa'] else 0,
            'has_top5_scores': len(b_scores) > 0 or len(br_scores) > 0,
            'submission_count': len(p_scores)
        })

    # Compute Top 5 Finalists & Titles
    prelim_sorted = sorted(candidates_data, key=lambda x: (x['final_score'], x['prelim_score']), reverse=True)
    top5_candidates = prelim_sorted[:5]

    titles = [
        "👑 MISS SK YOUTH AMBASSADRESS 2026",
        "👑 1st Runner-Up",
        "👑 2nd Runner-Up",
        "👑 3rd Runner-Up",
        "👑 4th Runner-Up"
    ]

    for idx, cand in enumerate(top5_candidates):
        cand['title'] = titles[idx]
        cand['top5_rank'] = idx + 1

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



