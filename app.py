from flask import Flask, request, render_template, jsonify, send_file
import csv
import os
import socket

app = Flask(__name__)

# Determine writable CSV location for Vercel serverless environment (/tmp) or local environment
CSV_FILE = '/tmp/pageant_scores.csv' if os.environ.get('VERCEL') else 'pageant_scores.csv'

def get_local_ip():
    """Auto-detect the local Wi-Fi / Hotspot IP address of the host laptop."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                'Candidate', 
                'Production (Max 100)', 'Casual Wear (Max 100)', 'Swimwear (Max 100)', 
                'Advocacy (Max 100)', 'Evening Gown (Max 100)', 'Q&A (Max 100)', 
                'FINAL SCORE', 'Judge'
            ])

# --- ROUTE 1: The Judges' Scoring Form ---
@app.route('/')
def home():
    host_ip = get_local_ip()
    return render_template('index.html', host_ip=host_ip)

# --- ROUTE 2: Saving Preliminary Scores (Form Data or JSON Offline Sync) ---
@app.route('/submit_score', methods=['POST'])
def save_score():
    init_csv()
    data = request.json if request.is_json else request.form
    
    candidate = data.get('candidate_number', '1')
    judge_name = data.get('judge_name', 'Judge 1')
    
    # 1. PRODUCTION (Sum to 100, Weight 15%)
    prod_sum = int(data.get('p_presence', 0)) + int(data.get('p_execution', 0)) + int(data.get('p_energy', 0)) + int(data.get('p_personality', 0))
    prod_weighted = prod_sum * 0.15

    # 2. CASUAL WEAR (Sum to 100, Weight 15%)
    cas_sum = int(data.get('c_poise', 0)) + int(data.get('c_carriage', 0)) + int(data.get('c_presence', 0)) + int(data.get('c_impact', 0))
    cas_weighted = cas_sum * 0.15

    # 3. SWIMWEAR (Sum to 100, Weight 15%)
    swim_sum = int(data.get('s_confidence', 0)) + int(data.get('s_carriage', 0)) + int(data.get('s_presence', 0)) + int(data.get('s_impact', 0))
    swim_weighted = swim_sum * 0.15

    # 4. ADVOCACY (Sum to 100, Weight 20%)
    adv_sum = int(data.get('a_relevance', 0)) + int(data.get('a_content', 0)) + int(data.get('a_feasibility', 0)) + int(data.get('a_communication', 0)) + int(data.get('a_sincerity', 0))
    adv_weighted = adv_sum * 0.20

    # 5. EVENING GOWN (Sum to 100, Weight 15%)
    gown_sum = int(data.get('e_elegance', 0)) + int(data.get('e_carriage', 0)) + int(data.get('e_grace', 0)) + int(data.get('e_styling', 0)) + int(data.get('e_impact', 0))
    gown_weighted = gown_sum * 0.15

    # 6. Q & A (Sum to 100, Weight 20%)
    qa_sum = int(data.get('q_relevance', 0)) + int(data.get('q_clarity', 0)) + int(data.get('q_insight', 0)) + int(data.get('q_communication', 0)) + int(data.get('q_composure', 0))
    qa_weighted = qa_sum * 0.20

    # GRAND TOTAL
    grand_total = prod_weighted + cas_weighted + swim_weighted + adv_weighted + gown_weighted + qa_weighted
    
    cand_label = candidate if str(candidate).startswith('Candidate') else f"Candidate {candidate}"

    # Save to CSV
    with open(CSV_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            cand_label, 
            prod_sum, cas_sum, swim_sum, adv_sum, gown_sum, qa_sum, round(grand_total, 2), judge_name
        ])
    
    if request.is_json:
        return jsonify({"status": "success", "message": f"Score for {cand_label} saved successfully!"})
    return "Score submitted successfully!"

# Helper to load scores logic
def get_leaderboard_data():
    results = {}
    init_csv()
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if 'Candidate' in row and row['Candidate']:
                    candidate = row['Candidate']
                    try:
                        score = float(row['FINAL SCORE'])
                    except (ValueError, KeyError):
                        continue
                    if candidate not in results:
                        results[candidate] = []
                    results[candidate].append(score)
    
    leaderboard = []
    for candidate, scores in results.items():
        avg_score = sum(scores) / len(scores)
        leaderboard.append({
            'candidate': candidate, 
            'score': round(avg_score, 2),
            'submissions': len(scores)
        })
        
    leaderboard.sort(key=lambda x: x['score'], reverse=True)
    return leaderboard

def get_admin_candidates_data():
    prelim_results = {}
    init_csv()
    
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if 'Candidate' in row and row['Candidate']:
                    try:
                        cand_num = int(row['Candidate'].replace('Candidate ', ''))
                        score = float(row['FINAL SCORE'])
                    except (ValueError, KeyError):
                        continue
                    if cand_num not in prelim_results:
                        prelim_results[cand_num] = []
                    prelim_results[cand_num].append(score)
    
    candidates_data = []
    for cand_num, scores in prelim_results.items():
        avg_score = sum(scores) / len(scores)
        candidates_data.append({
            'number': cand_num,
            'name': f"Candidate {cand_num}",
            'prelim_score': round(avg_score, 2),
            'count': len(scores)
        })
        
    candidates_data.sort(key=lambda x: x['number'])
    return candidates_data

# --- ROUTE 3: The Live Leaderboard ---
@app.route('/rankings')
def rankings():
    host_ip = get_local_ip()
    leaderboard = get_leaderboard_data()
    return render_template('rankings.html', leaderboard=leaderboard, host_ip=host_ip)

# --- ROUTE 4: ADMIN TABULATION (Top 5 Selection) ---
@app.route('/admin')
def admin_panel():
    host_ip = get_local_ip()
    candidates_data = get_admin_candidates_data()
    return render_template('admin.html', candidates=candidates_data, host_ip=host_ip)

# --- API ROUTE: Live Network Info & Status ---
@app.route('/api/network_info')
def network_info():
    host_ip = get_local_ip()
    total = 0
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='r') as file:
            total = max(0, sum(1 for _ in file) - 1)
    return jsonify({
        "host_ip": host_ip,
        "port": 5000,
        "mode": "Offline Hotspot Network",
        "total_submissions": total
    })

# --- API ROUTE: Live Rankings Polling ---
@app.route('/api/rankings_data')
def rankings_data():
    return jsonify({"leaderboard": get_leaderboard_data()})

# --- API ROUTE: Live Admin Polling ---
@app.route('/api/admin_data')
def admin_data():
    return jsonify({"candidates": get_admin_candidates_data()})

# --- API ROUTE: Reset Scores ---
@app.route('/api/reset_scores', methods=['POST'])
def reset_scores():
    with open(CSV_FILE, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            'Candidate', 
            'Production (Max 100)', 'Casual Wear (Max 100)', 'Swimwear (Max 100)', 
            'Advocacy (Max 100)', 'Evening Gown (Max 100)', 'Q&A (Max 100)', 
            'FINAL SCORE', 'Judge'
        ])
    return jsonify({"status": "success", "message": "All preliminary scores reset successfully!"})

# --- API ROUTE: Download CSV ---
@app.route('/download_csv')
def download_csv():
    init_csv()
    return send_file(CSV_FILE, as_attachment=True, download_name='pageant_scores.csv', mimetype='text/csv')

if __name__ == '__main__':
    init_csv()
    ip = get_local_ip()
    print("=" * 65)
    print("         SK FEDERATION PAGEANT TABULATION SERVER")
    print("         OFFLINE WI-FI HOTSPOT MODE ACTIVE")
    print("=" * 65)
    print(f" -> Judges Scoring Form:  http://{ip}:5000")
    print(f" -> Public Live Ranking: http://{ip}:5000/rankings")
    print(f" -> Admin Tabulation:    http://{ip}:5000/admin")
    print("=" * 65)
    app.run(host='0.0.0.0', port=5000, debug=False)
