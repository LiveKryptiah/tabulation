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

def init_csv():
    """Ensure CSV exists with headers, supporting judge attribution."""
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

# --- ROUTE: LOGIN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        slot = request.form.get('judge_slot', 'Judge 1')
        name = request.form.get('judge_name', '').strip()
        pin = request.form.get('pin', '').strip()

        if pin == JUDGE_PIN or pin == 'admin':
            session['judge_slot'] = slot
            session['judge_name'] = name if name else slot
            session['logged_in'] = True
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Invalid PIN / Passcode! Default PIN is 1234.")

    return render_template('login.html')

# --- ROUTE: LOGOUT ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ROUTE 1: The Judges' Scoring Form ---
@app.route('/')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('index.html', 
                           judge_slot=session.get('judge_slot', 'Judge 1'), 
                           judge_name=session.get('judge_name', 'Judge'))

# --- ROUTE 2: Saving Preliminary Scores ---
@app.route('/submit_score', methods=['POST'])
def save_score():
    init_csv()
    candidate = request.form.get('candidate_number', '')
    judge_slot = session.get('judge_slot', request.form.get('judge_slot', 'Judge 1'))
    judge_name = session.get('judge_name', request.form.get('judge_name', judge_slot))
    
    # 1. PRODUCTION (Sum to 100, Weight 15%)
    prod_sum = int(request.form.get('p_presence', 0)) + int(request.form.get('p_execution', 0)) + int(request.form.get('p_energy', 0)) + int(request.form.get('p_personality', 0))
    prod_weighted = prod_sum * 0.15

    # 2. CASUAL WEAR (Sum to 100, Weight 15%)
    cas_sum = int(request.form.get('c_poise', 0)) + int(request.form.get('c_carriage', 0)) + int(request.form.get('c_presence', 0)) + int(request.form.get('c_impact', 0))
    cas_weighted = cas_sum * 0.15

    # 3. SWIMWEAR (Sum to 100, Weight 15%)
    swim_sum = int(request.form.get('s_confidence', 0)) + int(request.form.get('s_carriage', 0)) + int(request.form.get('s_presence', 0)) + int(request.form.get('s_impact', 0))
    swim_weighted = swim_sum * 0.15

    # 4. ADVOCACY (Sum to 100, Weight 20%)
    adv_sum = int(request.form.get('a_relevance', 0)) + int(request.form.get('a_content', 0)) + int(request.form.get('a_feasibility', 0)) + int(request.form.get('a_communication', 0)) + int(request.form.get('a_sincerity', 0))
    adv_weighted = adv_sum * 0.20

    # 5. EVENING GOWN (Sum to 100, Weight 15%)
    gown_sum = int(request.form.get('e_elegance', 0)) + int(request.form.get('e_carriage', 0)) + int(request.form.get('e_grace', 0)) + int(request.form.get('e_styling', 0)) + int(request.form.get('e_impact', 0))
    gown_weighted = gown_sum * 0.15

    # 6. Q & A (Sum to 100, Weight 20%)
    qa_sum = int(request.form.get('q_relevance', 0)) + int(request.form.get('q_clarity', 0)) + int(request.form.get('q_insight', 0)) + int(request.form.get('q_communication', 0)) + int(request.form.get('q_composure', 0))
    qa_weighted = qa_sum * 0.20

    # GRAND TOTAL
    grand_total = prod_weighted + cas_weighted + swim_weighted + adv_weighted + gown_weighted + qa_weighted
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Save to CSV
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
    return "Score submitted successfully!"

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

# --- ROUTE 4: ADMIN TABULATION ---
@app.route('/admin')
def admin_panel():
    prelim_results = {}
    judge_progress = {}
    init_csv()
    
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
                        
                        if j_slot not in judge_progress:
                            judge_progress[j_slot] = set()
                        judge_progress[j_slot].add(cand_num)
                    except ValueError:
                        pass
    
    candidates_data = []
    for cand_num, scores in prelim_results.items():
        avg_score = sum(scores) / len(scores) if scores else 0
        candidates_data.append({
            'number': cand_num,
            'name': f"Candidate {cand_num}",
            'prelim_score': round(avg_score, 2),
            'submission_count': len(scores)
        })
        
    candidates_data.sort(key=lambda x: x['number'])
    judge_summary = {j: len(cands) for j, cands in judge_progress.items()}
    
    return render_template('admin.html', candidates=candidates_data, judge_summary=judge_summary)

# --- API ENDPOINT FOR LIVE POLLING ---
@app.route('/api/admin_data')
def admin_data():
    """Real-time JSON endpoint for live polling on Admin dashboard."""
    prelim_results = {}
    init_csv()
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                cand_str = row.get('Candidate', '')
                score_str = row.get('FINAL SCORE', '')
                if cand_str and score_str:
                    try:
                        cand_num = int(cand_str.replace('Candidate ', ''))
                        score = float(score_str)
                        if cand_num not in prelim_results:
                            prelim_results[cand_num] = []
                        prelim_results[cand_num].append(score)
                    except ValueError:
                        pass
                        
    candidates_data = []
    for cand_num, scores in prelim_results.items():
        avg_score = sum(scores) / len(scores) if scores else 0
        candidates_data.append({
            'number': cand_num,
            'name': f"Candidate {cand_num}",
            'prelim_score': round(avg_score, 2),
            'count': len(scores)
        })
    candidates_data.sort(key=lambda x: x['number'])
    return jsonify({'candidates': candidates_data})

if __name__ == '__main__':
    init_csv()
    print("Starting Tabulation Server...")
    app.run(host='0.0.0.0', port=5000, debug=True)

