from flask import Flask, request, render_template
import csv
import os

app = Flask(__name__)

# --- ROUTE 1: The Judges' Scoring Form ---
@app.route('/')
def home():
    return render_template('index.html')

# --- ROUTE 2: Saving Preliminary Scores ---
@app.route('/submit_score', methods=['POST'])
def save_score():
    candidate = request.form['candidate_number']
    
    # 1. PRODUCTION (Sum to 100, Weight 15%)
    prod_sum = int(request.form['p_presence']) + int(request.form['p_execution']) + int(request.form['p_energy']) + int(request.form['p_personality'])
    prod_weighted = prod_sum * 0.15

    # 2. CASUAL WEAR (Sum to 100, Weight 15%)
    cas_sum = int(request.form['c_poise']) + int(request.form['c_carriage']) + int(request.form['c_presence']) + int(request.form['c_impact'])
    cas_weighted = cas_sum * 0.15

    # 3. SWIMWEAR (Sum to 100, Weight 15%)
    swim_sum = int(request.form['s_confidence']) + int(request.form['s_carriage']) + int(request.form['s_presence']) + int(request.form['s_impact'])
    swim_weighted = swim_sum * 0.15

    # 4. ADVOCACY (Sum to 100, Weight 20%)
    adv_sum = int(request.form['a_relevance']) + int(request.form['a_content']) + int(request.form['a_feasibility']) + int(request.form['a_communication']) + int(request.form['a_sincerity'])
    adv_weighted = adv_sum * 0.20

    # 5. EVENING GOWN (Sum to 100, Weight 15%)
    gown_sum = int(request.form['e_elegance']) + int(request.form['e_carriage']) + int(request.form['e_grace']) + int(request.form['e_styling']) + int(request.form['e_impact'])
    gown_weighted = gown_sum * 0.15

    # 6. Q & A (Sum to 100, Weight 20%)
    qa_sum = int(request.form['q_relevance']) + int(request.form['q_clarity']) + int(request.form['q_insight']) + int(request.form['q_communication']) + int(request.form['q_composure'])
    qa_weighted = qa_sum * 0.20

    # GRAND TOTAL
    grand_total = prod_weighted + cas_weighted + swim_weighted + adv_weighted + gown_weighted + qa_weighted
    
    # Save to CSV
    with open('pageant_scores.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            "Candidate " + candidate, 
            prod_sum, cas_sum, swim_sum, adv_sum, gown_sum, qa_sum, round(grand_total, 2)
        ])
    return "Score submitted successfully!"

# --- ROUTE 3: The Live Leaderboard ---
@app.route('/rankings')
def rankings():
    results = {}
    if os.path.exists('pageant_scores.csv'):
        with open('pageant_scores.csv', mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if 'Candidate' in row and row['Candidate']:
                    candidate = row['Candidate']
                    score = float(row['FINAL SCORE'])
                    if candidate not in results:
                        results[candidate] = []
                    results[candidate].append(score)
    
    leaderboard = []
    for candidate, scores in results.items():
        avg_score = sum(scores) / len(scores)
        leaderboard.append({'candidate': candidate, 'score': round(avg_score, 2)})
        
    leaderboard.sort(key=lambda x: x['score'], reverse=True)
    return render_template('rankings.html', leaderboard=leaderboard)

# --- ROUTE 4: NEW ADMIN TABULATION (Top 5 Selection) ---
@app.route('/admin')
def admin_panel():
    prelim_results = {}
    
    # Read the preliminary scores from the CSV
    if os.path.exists('pageant_scores.csv'):
        with open('pageant_scores.csv', mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if 'Candidate' in row and row['Candidate']:
                    # Strip "Candidate " text so we can sort them numerically
                    cand_num = int(row['Candidate'].replace('Candidate ', ''))
                    score = float(row['FINAL SCORE'])
                    if cand_num not in prelim_results:
                        prelim_results[cand_num] = []
                    prelim_results[cand_num].append(score)
    
    # Average them out for the admin dashboard
    candidates_data = []
    for cand_num, scores in prelim_results.items():
        avg_score = sum(scores) / len(scores)
        candidates_data.append({
            'number': cand_num,
            'name': f"Candidate {cand_num}",
            'prelim_score': round(avg_score, 2)
        })
        
    # Sort nicely by Candidate Number (1, 2, 3...)
    candidates_data.sort(key=lambda x: x['number'])
    
    return render_template('admin.html', candidates=candidates_data)

if __name__ == '__main__':
    if not os.path.exists('pageant_scores.csv'):
        with open('pageant_scores.csv', mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                'Candidate', 
                'Production (Max 100)', 'Casual Wear (Max 100)', 'Swimwear (Max 100)', 
                'Advocacy (Max 100)', 'Evening Gown (Max 100)', 'Q&A (Max 100)', 
                'FINAL SCORE'
            ])

    print("Starting Server...")
    print("-> Judges go to:   http://[Your-IP-Address]")
    print("-> Public Ranking: http://[Your-IP-Address]/rankings")
    print("-> Admin Top 5:    http://[Your-IP-Address]/admin")
    app.run(host='0.0.0.0', port=80)