import os, json, sqlite3, threading
from datetime import datetime
from flask import Flask, request, jsonify
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, HRFlowable)
from reportlab.lib.enums import TA_CENTER

app   = Flask(__name__)
DB    = 'rapports.db'
PDFS  = 'rapports_pdf'
os.makedirs(PDFS, exist_ok=True)

# ── Base de données ──────────────────────────
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rapports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT, prenom TEXT, responsable TEXT, departement TEXT,
        heure_debut_journee TEXT, heure_fin_journee TEXT,
        date TEXT, timestamp TEXT, taches TEXT,
        commandes TEXT, signature TEXT, pdf_path TEXT, lu INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS commandes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rapport_id INTEGER, nom TEXT, prenom TEXT, departement TEXT,
        reference_piece TEXT, designation TEXT, quantite TEXT,
        urgence TEXT DEFAULT "Normal", commentaire TEXT,
        date TEXT, statut TEXT DEFAULT "En attente"
    )''')
    conn.commit()
    conn.close()

# ── Génération PDF ───────────────────────────
def generate_pdf(data, rapport_id):
    safe = data.get('nom','X').replace(' ','_')
    safe_date = (data.get('date') or 'date').replace('/', '-')
    path = os.path.join(PDFS, f'rapport_{rapport_id:04d}_{safe}_{safe_date}.pdf')

    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm,  bottomMargin=2.5*cm)
    styles = getSampleStyleSheet()
    S_TITLE = ParagraphStyle('t', fontSize=17, alignment=TA_CENTER,
                              fontName='Helvetica-Bold',
                              textColor=colors.HexColor('#1a4f8a'))
    S_SEC   = ParagraphStyle('s', fontSize=11, fontName='Helvetica-Bold',
                              textColor=colors.HexColor('#1a4f8a'),
                              spaceBefore=8, spaceAfter=4)

    story = [
        Paragraph('RAPPORT JOURNALIER DE MAINTENANCE', S_TITLE),
        HRFlowable(width='100%', thickness=2, color=colors.HexColor('#1a4f8a')),
        Spacer(1, 0.4*cm),
        Paragraph('INFORMATIONS TECHNICIEN', S_SEC),
    ]

    info_rows = [
        ['Nom', f"{data.get('nom','')} {data.get('prenom','')}", 'Date', data.get('date','')],
        ['Responsable', data.get('responsable',''), 'Département', data.get('departement','')],
        ['Heure début', data.get('heure_debut_journee',''), 'Heure fin', data.get('heure_fin_journee','')],
    ]
    t = Table(info_rows, colWidths=[3.5*cm,5.5*cm,3.5*cm,5.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,-1),colors.HexColor('#d6eaf8')),
        ('BACKGROUND',(2,0),(2,-1),colors.HexColor('#d6eaf8')),
        ('FONTNAME',(0,0),(-1,-1),'Helvetica'),
        ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
        ('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('PADDING',(0,0),(-1,-1),6),
    ]))
    story += [t, Spacer(1,0.5*cm)]

    taches = data.get('taches', [])
    if taches:
        story.append(Paragraph(f'TÂCHES EFFECTUÉES ({len(taches)})', S_SEC))
        header = [['#','Machine','Panne','Tâche effectuée','Début','Fin']]
        rows   = [[str(i), t.get('nom_machine',''),
                   Paragraph(t.get('panne',''), ParagraphStyle('p',fontSize=8)),
                   Paragraph(t.get('tache_effectuee',''), ParagraphStyle('p',fontSize=8)),
                   t.get('heure_debut',''), t.get('heure_fin','')]
                  for i,t in enumerate(taches,1)]
        tt = Table(header+rows, colWidths=[0.7*cm,3*cm,4*cm,5*cm,1.6*cm,1.7*cm])
        tt.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1a4f8a')),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),8),
            ('GRID',(0,0),(-1,-1),0.4,colors.lightgrey),
            ('PADDING',(0,0),(-1,-1),5),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#eaf4fc')]),
            ('VALIGN',(0,0),(-1,-1),'TOP'),
        ]))
        story += [tt, Spacer(1,0.5*cm)]

    commandes = data.get('commandes', [])
    if commandes:
        story.append(Paragraph(f'COMMANDES DE PIÈCES ({len(commandes)})', S_SEC))
        ch = [['Référence','Désignation','Qté','Urgence','Commentaire']]
        cr = [[c.get('reference_piece',''), c.get('designation',''),
               c.get('quantite',''), c.get('urgence',''), c.get('commentaire','')]
              for c in commandes]
        ct = Table(ch+cr, colWidths=[3*cm,4.5*cm,1.8*cm,2.2*cm,6.5*cm])
        ct.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#d35400')),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),8),
            ('GRID',(0,0),(-1,-1),0.4,colors.lightgrey),
            ('PADDING',(0,0),(-1,-1),5),
        ]))
        story += [ct, Spacer(1,0.5*cm)]

    story += [
        HRFlowable(width='100%', thickness=1, color=colors.grey),
        Spacer(1, 0.3*cm),
        Table([['Signature du Technicien :', 'Visa / Cachet Responsable :']],
              colWidths=[9*cm, 9*cm])
    ]
    doc.build(story)
    return path

# ── Routes Flask ─────────────────────────────
@app.route('/ping')
def ping():
    return jsonify({'status': 'ok'})

@app.route('/api/rapport', methods=['POST'])
def receive():
    try:
        data = request.json
        conn = sqlite3.connect(DB)
        c    = conn.cursor()

        c.execute('''INSERT INTO rapports
            (nom,prenom,responsable,departement,heure_debut_journee,
             heure_fin_journee,date,timestamp,taches,commandes,signature,pdf_path)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', (
            data.get('nom',''), data.get('prenom',''),
            data.get('responsable',''), data.get('departement',''),
            data.get('heure_debut_journee',''), data.get('heure_fin_journee',''),
            data.get('date',''),
            data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            json.dumps(data.get('taches',[]),    ensure_ascii=False),
            json.dumps(data.get('commandes',[]), ensure_ascii=False),
            json.dumps(data.get('signature',[]), ensure_ascii=False),
            ''
        ))
        rid = c.lastrowid

        for cmd in data.get('commandes', []):
            c.execute('''INSERT INTO commandes
                (rapport_id,nom,prenom,departement,reference_piece,
                 designation,quantite,urgence,commentaire,date)
                VALUES(?,?,?,?,?,?,?,?,?,?)''', (
                rid, data.get('nom',''), data.get('prenom',''),
                data.get('departement',''),
                cmd.get('reference_piece',''), cmd.get('designation',''),
                cmd.get('quantite',''), cmd.get('urgence','Normal'),
                cmd.get('commentaire',''), data.get('date','')
            ))

        conn.commit()
        pdf = generate_pdf(data, rid)
        c.execute('UPDATE rapports SET pdf_path=? WHERE id=?', (pdf, rid))
        conn.commit()
        conn.close()

        return jsonify({'status':'success','id':rid})
    except Exception as e:
        return jsonify({'status':'error','message':str(e)}), 500

# ── Endpoints pour le logiciel PC ────────────
@app.route('/api/rapports')
def list_rapports():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('SELECT id,date,nom,prenom,departement,responsable,taches,commandes,lu FROM rapports ORDER BY id DESC')
    rows = c.fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            'id':r[0],'date':r[1],'nom':r[2],'prenom':r[3],
            'departement':r[4],'responsable':r[5],
            'nb_taches':len(json.loads(r[6])),
            'nb_commandes':len(json.loads(r[7])),
            'lu':r[8]
        })
    return jsonify(result)

@app.route('/api/rapport/<int:rid>')
def get_rapport(rid):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('SELECT * FROM rapports WHERE id=?', (rid,))
    row = c.fetchone()
    c.execute('UPDATE rapports SET lu=1 WHERE id=?', (rid,))
    conn.commit()
    conn.close()
    if not row:
        return jsonify({'error':'not found'}), 404
    cols = ['id','nom','prenom','responsable','departement',
            'heure_debut_journee','heure_fin_journee','date',
            'timestamp','taches','commandes','signature','pdf_path','lu']
    d = dict(zip(cols, row))
    d['taches']    = json.loads(d['taches'])
    d['commandes'] = json.loads(d['commandes'])
    return jsonify(d)

@app.route('/api/pdf/<int:rid>')
def download_pdf(rid):
    from flask import send_file
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('SELECT pdf_path FROM rapports WHERE id=?', (rid,))
    row = c.fetchone()
    conn.close()
    if row and row[0] and os.path.exists(row[0]):
        return send_file(row[0], as_attachment=True)
    return jsonify({'error':'PDF not found'}), 404

@app.route('/api/commandes')
def list_commandes():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''SELECT id,date,nom||" "||prenom,departement,
                        reference_piece,designation,quantite,urgence,commentaire,statut
                 FROM commandes ORDER BY
                    CASE urgence WHEN "Critique" THEN 1 WHEN "Urgent" THEN 2 ELSE 3 END''')
    rows = c.fetchall()
    conn.close()
    keys = ['id','date','technicien','departement','reference',
            'designation','quantite','urgence','commentaire','statut']
    return jsonify([dict(zip(keys,r)) for r in rows])

@app.route('/api/commande/<int:cid>/statut', methods=['PUT'])
def update_statut(cid):
    data   = request.json
    statut = data.get('statut','En attente')
    conn   = sqlite3.connect(DB)
    c      = conn.cursor()
    c.execute('UPDATE commandes SET statut=? WHERE id=?', (statut, cid))
    conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

@app.route('/api/stats')
def stats():
    conn = sqlite3.connect(DB)
    c    = conn.cursor()
    today = datetime.now().strftime('%d/%m/%Y')
    month = datetime.now().strftime('%m/%Y')
    c.execute('SELECT COUNT(*) FROM rapports')
    total = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM rapports WHERE date=?', (today,))
    today_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM commandes WHERE statut='En attente'")
    pending = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT nom||' '||prenom) FROM rapports WHERE date LIKE ?",
              (f'%/{month}',))
    techs = c.fetchone()[0]
    conn.close()
    return jsonify({'total':total,'today':today_count,'pending':pending,'techs':techs})

# ── Démarrage ────────────────────────────────
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)