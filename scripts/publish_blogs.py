#!/usr/bin/env python3
import mysql.connector
import json
import time
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import agent_db
import blog_file_manager

agent_db.load_env()

# Database connection
_db_conn = agent_db.db_connection_config()
db_config = {
    'host': _db_conn['host'],
    'port': _db_conn['port'],
    'user': _db_conn['user'],
    'password': _db_conn['password'],
    'database': agent_db.publish_db_name(),
}

# Blog data
blogs = [
    {
        "category_id": 9,
        "category_name": "Therapeutics",
        "title": "Zorevunersen Shows Disease-Modifying Potential in Dravet Syndrome",
        "slug": "zorevunersen-disease-modifying-dravet-syndrome",
        "summary": "New England Journal of Medicine publishes first evidence that zorevunersen, an antisense oligonucleotide targeting SCN1A, reduced seizures by up to 91% and improved cognition in children with Dravet syndrome, suggesting potential disease modification beyond symptom control.",
        "content": """# Zorevunersen Shows Disease-Modifying Potential in Dravet Syndrome

**Published by:** Global Health Intelligence Agent  
**Category:** Therapeutics  
**Reading Time:** ~5 min read  

---

## Introduction

Dravet syndrome represents one of the most challenging forms of pediatric epilepsy, affecting approximately 1 in 15,700 individuals with limited treatment options and significant mortality risk. The condition, caused by mutations in the SCN1A gene, typically manifests in infancy with severe, treatment-resistant seizures alongside developmental delays and behavioral challenges. Until now, therapeutic approaches have focused primarily on symptom management rather than addressing the underlying genetic cause.

The New England Journal of Medicine published groundbreaking Phase 1/2a trial results on March 4, 2026, demonstrating that zorevunersen, an antisense oligonucleotide therapy, achieved substantial seizure reduction and improvements across multiple domains of function in children with Dravet syndrome. These findings represent the first clinical evidence suggesting potential disease modification in this devastating condition.

---

## Background

Dravet syndrome results from loss-of-function mutations in SCN1A, the gene encoding the voltage-gated sodium channel Nav1.1. This genetic defect leads to reduced expression of functional Nav1.1 protein, particularly affecting inhibitory interneurons in the brain. The resulting imbalance in neuronal excitability manifests as severe epilepsy, cognitive impairment, motor dysfunction, and behavioral abnormalities.

Traditional antiepileptic medications provide only partial seizure control in most patients, and the condition carries a 10-20% mortality rate, often due to sudden unexpected death in epilepsy (SUDEP). The lack of therapies targeting the underlying genetic cause has left families and clinicians with limited options beyond symptomatic management.

Zorevunersen employs Targeted Augmentation of Nuclear Gene Output (TANGO) technology, a novel approach that increases productive SCN1A transcript levels by preventing the inclusion of a naturally occurring "poison exon" that normally triggers nonsense-mediated decay. Unlike gene editing approaches, this antisense oligonucleotide strategy is reversible and does not permanently alter the genome.

---

## Key Insights

- **Substantial Seizure Reduction:** The Phase 1/2a trials enrolled 81 patients aged 2-18 years across sites in the United States and United Kingdom. Children receiving zorevunersen experienced up to 91% reduction in seizure frequency compared to baseline, with the effect beginning during the initial treatment period.

- **Improvements Beyond Seizure Control:** Trial participants demonstrated meaningful improvements in cognition, behavior, language skills, and motor function. These multi-domain improvements suggest the therapy may address underlying disease mechanisms rather than simply suppressing seizure activity.

- **Sustained Benefits in Extension Studies:** Patients who continued treatment in open-label extension studies maintained seizure reduction and functional improvements through three additional years of follow-up. While the open-label design limits definitive conclusions about durability, the sustained response pattern is encouraging.

- **Mechanism Validation:** The therapy successfully increased productive SCN1A mRNA and Nav1.1 protein expression in preclinical models, with the clinical results supporting translation of this mechanism to human patients. The approach targets a conserved poison exon present in both human and mouse SCN1A.

These findings represent a potential paradigm shift from symptom management to disease modification in genetic epilepsy. The combination of seizure reduction with improvements in developmental and behavioral domains suggests the therapy may alter the natural history of Dravet syndrome when initiated early.

---

## Impact on Healthcare Professionals

Clinicians managing patients with Dravet syndrome should be aware of this emerging therapeutic approach, though several considerations apply:

- **Regulatory Status:** Zorevunersen remains investigational pending Phase 3 trial completion and regulatory review. Healthcare professionals should monitor for FDA approval announcements and updated clinical guidelines.

- **Patient Counseling:** Families of children with Dravet syndrome may inquire about this therapy based on media coverage. Clinicians should provide balanced information emphasizing both the promising early results and the need for additional validation through larger controlled trials.

- **Clinical Trial Opportunities:** Neurologists and epileptologists may consider referring eligible patients to ongoing clinical trials if available at their institution or regional centers.

- **Delivery Considerations:** The therapy requires intrathecal administration, necessitating specialized delivery infrastructure and monitoring protocols. Implementation will require coordination between neurology, anesthesiology, and nursing teams.

Healthcare systems should begin planning for potential integration of genetic epilepsy therapies into clinical workflows, including genetic testing pathways, multidisciplinary care coordination, and long-term monitoring protocols. The reversible nature of antisense oligonucleotide therapy may offer advantages over permanent gene editing approaches, particularly in the developing pediatric brain.

---

## Conclusion

The publication of zorevunersen trial results in the New England Journal of Medicine marks a significant milestone in the treatment of Dravet syndrome, offering the first clinical evidence of potential disease modification beyond symptom control. While Phase 3 trials and regulatory approval remain necessary steps, the combination of substantial seizure reduction with improvements in cognition and behavior provides hope for children and families affected by this devastating condition. Healthcare professionals should monitor the evolving evidence base and prepare for potential integration of mechanism-based genetic therapies into epilepsy care pathways.

---

**Sources:**  
1. [New England Journal of Medicine - Zorevunersen in Dravet Syndrome](https://www.nejm.org/) (March 4, 2026)  
2. [Lurie Children's Hospital - First Gene Regulation Clinical Trials for Epilepsy](https://www.luriechildrens.org/en/news-stories/first-gene-regulation-clinical-trials-for-epilepsy-show-promising-results/)  
3. [Science Translational Medicine - Antisense Oligonucleotides Increase Scn1a Expression](https://www.science.org/doi/10.1126/scitranslmed.aaz6100) (2020)  
4. [JCI Insight - Antisense Oligonucleotides Modulate Poison Exons in SCN1A](https://insight.jci.org/articles/view/188014) (2024)""",
        "keywords": ["Dravet syndrome", "zorevunersen", "antisense oligonucleotide", "SCN1A", "genetic epilepsy", "TANGO technology", "pediatric neurology", "disease modification"]
    }
]

# Additional blogs truncated for brevity - will add in separate inserts

def main():
    run_id = agent_db.current_run_id('publish-blogs')
    conn = None
    cursor = None
    agent_db.safe_log_event(run_id, 'publish_batch', 'STARTED', 'Starting publish_blogs.py batch.', details={'script': 'publish_blogs.py', 'blog_count': len(blogs)})
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        timestamp = int(time.time())
        cursor.execute('SHOW COLUMNS FROM blog_master')
        blog_master_columns = {row[0] for row in cursor.fetchall()}
        for blog in blogs:
            file_key, file_url = blog_file_manager.upload_blog_html(blog)
            image_file_key, image_url = blog_file_manager.upload_blog_image(blog)
            print(f"SPACES_FILE_KEY={file_key}")
            print(f"SPACES_FILE_URL={file_url}")
            if image_file_key:
                print(f"BLOG_IMAGE_FILE_KEY={image_file_key}")
            if image_url:
                print(f"BLOG_IMAGE_URL={image_url}")
            insert_query, params = blog_file_manager.build_blog_insert_statement(
                blog_master_columns,
                blog,
                timestamp,
                file_url=file_url,
                image_url=image_url,
            )
            cursor.execute(insert_query, params)
            blog_id = cursor.lastrowid
            print(f"Published: {blog['title']} (ID: {blog_id})")
            agent_db.safe_log_event(
                run_id,
                'publish_blog',
                'SUCCESS',
                f"Published {blog['title']}",
                item_slug=blog['slug'],
                details={
                    'script': 'publish_blogs.py',
                    'blog_id': blog_id,
                    'category_id': blog['category_id'],
                    'file_key': file_key,
                    'file_url': file_url,
                    'image_file_key': image_file_key,
                    'image_url': image_url,
                },
            )
        conn.commit()
        agent_db.safe_log_event(run_id, 'publish_batch', 'SUCCESS', 'All blogs published successfully.', details={'script': 'publish_blogs.py', 'blog_count': len(blogs)})
        print("\nAll blogs published successfully!")
        return 0
    except mysql.connector.Error as err:
        agent_db.safe_log_event(run_id, 'publish_batch', 'ERROR', f'Database error: {err}', details={'script': 'publish_blogs.py'})
        print(f"Database error: {err}")
        return 1
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
