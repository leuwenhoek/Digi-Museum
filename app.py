from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import sqlite3
import random
from datetime import datetime
import json # New Import

# --- NEW IMPORTS for Gemini AI and .env ---
from dotenv import load_dotenv
from google import genai 
from google.genai import types # New Import

# Load environment variables from .env file immediately
load_dotenv()
# --- END NEW IMPORTS ---


app = Flask(__name__)
# IMPORTANT: Change this in production
app.secret_key = 'your-secret-key-here-change-in-production' 

# Use the Flask instance folder for the DB
db_path = os.path.join(app.instance_path, 'museum_app.db')
os.makedirs(app.instance_path, exist_ok=True)


# --- GEMINI API HELPERS ---

# Define the structured output for the quiz
QUIZ_SCHEMA = {
    "type": "object",
    "properties": {
        "quiz_title": {"type": "string", "description": "A catchy title for the quiz."},
        "questions": {
            "type": "array",
            "description": "A list of 5 multiple-choice questions about the museum.",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The quiz question."},
                    "options": {
                        "type": "array",
                        "description": "Exactly four answer options.",
                        "items": {"type": "string"}
                    },
                    "answer": {"type": "string", "description": "The correct answer option (must match one of the options in the list exactly)."}
                },
                "required": ["question", "options", "answer"]
            }
        }
    },
    "required": ["quiz_title", "questions"]
}

def get_museum_summary(museum_name, city):
    """
    Calls the Gemini API to get a summary of a museum. (Existing function)
    """
    try:
        # The client automatically picks up the GEMINI_API_KEY from the environment
        client = genai.Client() 
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")
        return "AI summary service unavailable. Check your GEMINI_API_KEY."

    prompt = (
        f"Provide a concise, engaging, and factual summary of the {museum_name} in {city}. "
        f"The summary should be about 3-4 sentences long and focus on its historical significance or main collections."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"Error calling Gemini API for {museum_name}: {e}")
        return f"Could not fetch AI summary for {museum_name}."


def generate_quiz(museum_name, museum_city):
    """
    Calls the Gemini API to generate a multiple-choice quiz about a museum 
    and returns the data as a Python dictionary.
    """
    try:
        client = genai.Client()
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")
        return None

    prompt = (
        f"Generate a fun 5-question multiple-choice quiz about the {museum_name} in {museum_city}. "
        f"Each question must have exactly 4 options. The correct answer must be one of the options."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=QUIZ_SCHEMA
            )
        )
        # The response text is a JSON string, which we load into a dict
        quiz_data = json.loads(response.text)
        # Add a fallback for ensuring 5 questions, although the model usually adheres to the schema
        if len(quiz_data.get('questions', [])) != 5:
             raise ValueError("Generated quiz did not contain exactly 5 questions.")
        return quiz_data
    except Exception as e:
        print(f"Error calling Gemini API for quiz: {e}")
        # Return a simple fallback quiz on error
        return {
            "quiz_title": f"Fallback Quiz on {museum_name}",
            "questions": [
                {
                    "question": f"Which city is the {museum_name} located in?",
                    "options": [museum_city, "Mumbai", "Kolkata", "Delhi"],
                    "answer": museum_city
                },
                {
                    "question": "What is the primary purpose of a museum?",
                    "options": ["Entertainment", "Education and Preservation", "Shopping", "Sports"],
                    "answer": "Education and Preservation"
                },
                {
                    "question": "In which continent is India located?",
                    "options": ["Europe", "Africa", "Asia", "South America"],
                    "answer": "Asia"
                },
                {
                    "question": "The famous 'Dancing Girl' statuette belongs to which civilization?",
                    "options": ["Egyptian", "Mesopotamian", "Indus Valley", "Roman"],
                    "answer": "Indus Valley"
                },
                {
                    "question": "The term 'Mughal' refers to a dynasty from which country?",
                    "options": ["China", "India", "Turkey", "Mongolia"],
                    "answer": "Mongolia"
                }
            ]
        }
# --- END GEMINI API HELPERS ---


# --- CORE DATA MODEL: MUSEUM DIRECTORY (UNMODIFIED) ---
MUSEUM_DATA = {
    # Key: Used for URL slug (e.g., /museum/national_museum_new_delhi)
    'national_museum_new_delhi': {
        'name': 'National Museum',
        'city': 'New Delhi',
        'visitors_per_year': 800000,
        'weekday_charge': 20,
        'weekend_charge': 20,
        'hours': '10:00 AM - 6:00 PM (Closed on Monday)',
        'top_exhibits': [
            {'title': 'Dancing Girl of Mohenjo-daro', 'desc': 'A famous 4,500-year-old bronze statuette from the Indus Valley Civilization.', 'img': 'https://example.com/nm_dancing_girl.jpg'},
            {'title': 'Buddha Relics', 'desc': 'Original relics of the Buddha, displayed in the Buddhist Art Gallery.', 'img': 'https://example.com/nm_buddha_relics.jpg'},
            {'title': 'Nataraja Chola Bronze', 'desc': 'An exquisite 12th-century bronze of Shiva as the cosmic dancer.', 'img': 'https://example.com/nm_nataraja.jpg'},
            {'title': 'Akota Bronzes', 'desc': 'A collection of Jain images from Akota (Gujarat), dating to the 6th-12th centuries.', 'img': 'https://example.com/nm_akota_bronzes.jpg'},
            {'title': 'Mughal Miniature Paintings', 'desc': 'An extensive collection from the Mughal, Deccani, and Pahari schools of painting.', 'img': 'https://example.com/nm_miniatures.jpg'},
        ]
    },
    'indian_museum_kolkata': {
        'name': 'Indian Museum',
        'city': 'Kolkata',
        'visitors_per_year': 650000,
        'weekday_charge': 50,
        'weekend_charge': 50,
        'hours': '10:00 AM - 5:00 PM (Closed on Monday)',
        'top_exhibits': [
            {'title': 'Egyptian Mummy', 'desc': 'A 4,000-year-old human mummy from the Ptolemaic period.', 'img': 'https://example.com/im_mummy.jpg'},
            {'title': 'Bharhut Stupa Railings', 'desc': 'Original stone railings and gateways from the 2nd-century BCE Bharhut Stupa.', 'img': 'https://example.com/im_bharhut.jpg'},
            {'title': 'Ashoka Lion Capital (Copy)', 'desc': 'A replica of the Lion Capital of Ashoka, the national emblem of India.', 'img': 'https://example.com/im_ashoka.jpg'},
            {'title': 'Fossil Skeletons', 'desc': 'Includes the skeleton of a massive extinct elephant species.', 'img': 'https://example.com/im_fossil.jpg'},
            {'title': 'Buddha Preaching in Tushita Heaven', 'desc': 'A large stone panel from the Amaravati Stupa ruins.', 'img': 'https://example.com/im_buddha_amravati.jpg'},
        ]
    },
    'csmvs_mumbai': {
        'name': 'Chhatrapati Shivaji Maharaj Vastu Sangrahalaya',
        'city': 'Mumbai',
        'visitors_per_year': 1200000,
        'weekday_charge': 100,
        'weekend_charge': 120,
        'hours': '10:15 AM - 6:00 PM (Open 7 days)',
        'top_exhibits': [
            {'title': 'Indus Valley Artefacts', 'desc': 'Includes terracotta figurines and seals dating back to 3000 BC.', 'img': 'https://example.com/csmvs_indus.jpg'},
            {'title': 'The Sword of Damocles', 'desc': 'A famous 19th-century oil painting by Antoine Dubost on the theme of impending doom.', 'img': 'https://example.com/csmvs_sword.jpg'},
            {'title': 'Miniature Painting Gallery', 'desc': 'A wide collection covering Mughal, Rajasthani, and Pahari schools.', 'img': 'https://example.com/csmvs_miniature.jpg'},
            {'title': 'Mughal Jade Collection', 'desc': 'Intricately carved jade objects from the Mughal period.', 'img': 'https://example.com/csmvs_jade.jpg'},
            {'title': 'Bronze Armour of Emperor Akbar', 'desc': 'A finely decorated steel breastplate and shield, dated 1581 CE.', 'img': 'https://example.com/csmvs_armour.jpg'},
        ]
    },
    'salar_jung_museum_hyderabad': {
        'name': 'Salar Jung Museum',
        'city': 'Hyderabad',
        'visitors_per_year': 1500000,
        'weekday_charge': 50,
        'weekend_charge': 50,
        'hours': '10:00 AM - 6:00 PM (Closed on Friday)',
        'top_exhibits': [
            {'title': 'The Veiled Rebecca', 'desc': 'A marble sculpture by Italian artist G.B. Benzoni, famous for its realistic marble veil.', 'img': 'https://example.com/sjm_rebecca.jpg'},
            {'title': 'Musical Clock', 'desc': 'A 19th-century British clock where a miniature figure emerges to strike the gong every hour.', 'img': 'https://example.com/sjm_clock.jpg'},
            {'title': 'Chair of Tipu Sultan', 'desc': 'A beautifully carved gold-crested chair believed to belong to Tipu Sultan.', 'img': 'https://example.com/sjm_chair.jpg'},
            {'title': 'Collection of Qurans', 'desc': 'A rare collection of holy books written in various scripts and calligraphy.', 'img': 'https://example.com/sjm_quran.jpg'},
            {'title': 'Ivory Carved Dashavatara Shrine', 'desc': 'A detailed 18th-century ivory shrine depicting the ten avatars of Vishnu.', 'img': 'https://example.com/sjm_ivory.jpg'},
        ]
    },
    'bihar_museum_patna': {
        'name': 'Bihar Museum',
        'city': 'Patna',
        'visitors_per_year': 400000,
        'weekday_charge': 100,
        'weekend_charge': 100,
        'hours': '10:00 AM - 5:00 PM (Closed on Monday)',
        'top_exhibits': [
            {'title': 'Didarganj Yakshi', 'desc': 'A magnificent polished sandstone sculpture from the Mauryan period.', 'img': 'https://example.com/bm_yakshi.jpg'},
            {'title': 'Mauryan Dynasty Exhibits', 'desc': 'Artifacts detailing the rise and spread of the Mauryan empire.', 'img': 'https://example.com/bm_maurya.jpg'},
            {'title': 'Patna School of Painting', 'desc': 'Works showcasing the unique style of miniature painting from the Patna region.', 'img': 'https://example.com/bm_patna.jpg'},
            {'title': 'Regional Art Gallery', 'desc': 'Boasts unique artistic expressions and handicrafts of Bihar.', 'img': 'https://example.com/bm_regional.jpg'},
            {'title': 'Visible Storage Gallery', 'desc': 'A unique gallery providing a behind-the-scenes look at coin and terracotta artifacts.', 'img': 'https://example.com/bm_storage.jpg'},
        ]
    },
    'albert_hall_museum_jaipur': {
        'name': 'Albert Hall Museum',
        'city': 'Jaipur',
        'visitors_per_year': 950000,
        'weekday_charge': 50,
        'weekend_charge': 70,
        'hours': '9:00 AM - 5:00 PM (Open 7 days)',
        'top_exhibits': [
            {'title': 'Egyptian Mummy', 'desc': 'A 3,000-year-old mummy of a female named Tutu from the Ptolemaic era.', 'img': 'https://example.com/ahm_mummy.jpg'},
            {'title': 'Persian Carpets', 'desc': 'An exquisite collection of Persian and Mughal carpets, including a famous one depicting a hunting scene.', 'img': 'https://example.com/ahm_carpet.jpg'},
            {'title': 'Miniatures and Portraits', 'desc': 'Showcasing the distinct Jaipur school of art and royal portraits.', 'img': 'https://example.com/ahm_miniatures.jpg'},
            {'title': 'Pottery and Ceramics', 'desc': 'A diverse display of pottery, including traditional Rajasthani blue pottery.', 'img': 'https://example.com/ahm_pottery.jpg'},
            {'title': 'Metal Art Objects', 'desc': 'Decorative arts made from metal, showcasing Rajasthani craftsmanship.', 'img': 'https://example.com/ahm_metal.jpg'},
        ]
    },
    'calico_museum_of_textiles': {
        'name': 'Calico Museum of Textiles',
        'city': 'Ahmedabad',
        'visitors_per_year': 50000,
        'weekday_charge': 0,
        'weekend_charge': 0,
        'hours': '10:30 AM - 12:30 PM (Closed on Wednesday - Timed Entry)',
        'top_exhibits': [
            {'title': 'Court Textiles', 'desc': 'Rare fabrics worn by Mughal and provincial rulers from the 15th to 19th centuries.', 'img': 'https://example.com/cmt_court.jpg'},
            {'title': 'Regional Embroideries', 'desc': 'A stunning array of handcrafted embroideries from different parts of India.', 'img': 'https://example.com/cmt_embroidery.jpg'},
            {'title': 'Pichwais and Kalamkaris', 'desc': 'Exquisite religious narrative cloths, including painted and block-printed works.', 'img': 'https://example.com/cmt_kalamkari.jpg'},
            {'title': 'Kashmiri Shawls', 'desc': 'Fine Pashmina and Shahtoosh shawls with intricate weaving patterns.', 'img': 'https://example.com/cmt_shawls.jpg'},
            {'title': 'Costumes of Religious Sects', 'desc': 'Clothing and vestments used by various religious and mystic orders.', 'img': 'https://example.com/cmt_costumes.jpg'},
        ]
    },
    'national_rail_museum_new_delhi': {
        'name': 'National Rail Museum',
        'city': 'New Delhi',
        'visitors_per_year': 700000,
        'weekday_charge': 50,
        'weekend_charge': 100,
        'hours': '10:00 AM - 5:00 PM (Closed on Monday)',
        'top_exhibits': [
            {'title': 'Fairy Queen Steam Locomotive', 'desc': 'The oldest surviving operational steam locomotive in the world (1855).', 'img': 'https://example.com/nrm_fairy_queen.jpg'},
            {'title': 'Patiala State Monorail', 'desc': 'A unique monorail system that was operational in the princely state of Patiala.', 'img': 'https://example.com/nrm_monorail.jpg'},
            {'title': 'Saloon of the Maharaja of Mysore', 'desc': 'The luxurious private coach used by the Maharaja of Mysore.', 'img': 'https://example.com/nrm_mysore_saloon.jpg'},
            {'title': 'Fireless Steam Locomotive', 'desc': 'A rare locomotive that operated without fire, using stored steam power.', 'img': 'https://example.com/nrm_fireless.jpg'},
            {'title': 'Toy Train Ride', 'desc': 'A small train that provides a fun ride around the museum grounds.', 'img': 'https://example.com/nrm_toy_train.jpg'},
        ]
    },
    'government_museum_chennai': {
        'name': 'Government Museum',
        'city': 'Chennai',
        'visitors_per_year': 750000,
        'weekday_charge': 20,
        'weekend_charge': 20,
        'hours': '9:30 AM - 5:00 PM (Closed on Friday)',
        'top_exhibits': [
            {'title': 'Amravati Sculptures', 'desc': 'Massive marble sculptures from the ancient Buddhist stupa at Amaravati.', 'img': 'https://example.com/gm_amravati.jpg'},
            {'title': 'Bronze Gallery', 'desc': 'An extensive collection of exquisite Chola and Pallava bronze sculptures.', 'img': 'https://example.com/gm_bronze.jpg'},
            {'title': 'Contemporary Art Section', 'desc': 'Works by modern and contemporary artists from South India.', 'img': 'https://example.com/gm_art.jpg'},
            {'title': 'Children\'s Museum', 'desc': 'An interactive section dedicated to sparking curiosity in young minds.', 'img': 'https://example.com/gm_childrens.jpg'},
            {'title': 'Numismatics Gallery', 'desc': 'A large collection of coins tracing the history of South India.', 'img': 'https://example.com/gm_coins.jpg'},
        ]
    },
    'national_gallery_of_modern_art_new_delhi': {
        'name': 'National Gallery of Modern Art (NGMA)',
        'city': 'New Delhi',
        'visitors_per_year': 150000,
        'weekday_charge': 20,
        'weekend_charge': 20,
        'hours': '10:00 AM - 5:00 PM (Closed on Monday)',
        'top_exhibits': [
            {'title': 'Amrita Sher-gil Collection', 'desc': 'Key works by the renowned pioneer of modern Indian art, Amrita Sher-gil.', 'img': 'https://example.com/ngma_amrita.jpg'},
            {'title': 'S. H. Raza Paintings', 'desc': 'Abstract and contemporary works by the famous Indian artist, S. H. Raza.', 'img': 'https://example.com/ngma_raza.jpg'},
            {'title': 'Works by Rabindranath Tagore', 'desc': 'Original paintings and sketches by the Nobel laureate and artist.', 'img': 'https://example.com/ngma_tagore.jpg'},
            {'title': 'Man with Bouquet of Plastic Flowers', 'desc': 'A famous contemporary painting by Bhupen Khakhar.', 'img': 'https://example.com/ngma_khakhar.jpg'},
            {'title': 'Modern Indian Sculpture', 'desc': 'Sculptures showcasing the evolution of modern Indian form and technique.', 'img': 'https://example.com/ngma_sculpture.jpg'},
        ]
    },
    'shankar_international_dolls_museum': {
        'name': "Shankar's International Dolls Museum",
        'city': 'New Delhi',
        'visitors_per_year': 400000,
        'weekday_charge': 20,
        'weekend_charge': 20,
        'hours': '10:00 AM - 5:30 PM (Closed on Monday)',
        'top_exhibits': [
            {'title': 'Dolls from over 85 Countries', 'desc': 'A diverse collection of dolls representing cultures from around the world.', 'img': 'https://example.com/sdm_international.jpg'},
            {'title': 'Indian Regional Dolls', 'desc': 'Dolls representing the diverse costumes and cultures of India\'s states.', 'img': 'https://example.com/sdm_india.jpg'},
            {'title': 'Japanese Kabuki Dolls', 'desc': 'A delicate collection of traditional Japanese Kabuki dolls.', 'img': 'https://example.com/sdm_kabuki.jpg'},
            {'title': 'Bride Dolls', 'desc': 'A section dedicated to bridal costumes and traditions globally.', 'img': 'https://example.com/sdm_bride.jpg'},
            {'title': 'Children\'s Corner Dolls', 'desc': 'Fun and whimsical play dolls for children to view.', 'img': 'https://example.com/sdm_corner.jpg'},
        ]
    },
    'virasat_e_khalsa': {
        'name': 'Virasat-e-Khalsa',
        'city': 'Anandpur Sahib',
        'visitors_per_year': 1000000,
        'weekday_charge': 0,
        'weekend_charge': 0,
        'hours': '10:00 AM - 4:30 PM (Closed on Monday)',
        'top_exhibits': [
            {'title': 'History of Sikhism', 'desc': 'A chronological narrative gallery detailing the history and faith of Sikhism.', 'img': 'https://example.com/vek_sikhism.jpg'},
            {'title': 'Formation of Khalsa Panth', 'desc': 'Multimedia exhibits focusing on the pivotal events of 1699.', 'img': 'https://example.com/vek_khalsa.jpg'},
            {'title': 'Architectural Wonder', 'desc': 'The unique, modern design of the building itself, symbolizing the hands of prayer.', 'img': 'https://example.com/vek_arch.jpg'},
            {'title': 'Historical Manuscripts', 'desc': 'Rare manuscripts and historical documents related to the Gurus.', 'img': 'https://example.com/vek_manuscripts.jpg'},
            {'title': 'Sikh Heritage Galleries', 'desc': 'Galleries using immersive technology to tell stories of the Sikh Gurus.', 'img': 'https://example.com/vek_heritage.jpg'},
        ]
    },
    'napier_museum_thiruvananthapuram': {
        'name': 'Napier Museum',
        'city': 'Thiruvananthapuram',
        'visitors_per_year': 300000,
        'weekday_charge': 20,
        'weekend_charge': 20,
        'hours': '10:00 AM - 5:00 PM (Closed on Monday)',
        'top_exhibits': [
            {'title': 'Bronze Idols (Chola, Chera)', 'desc': 'An excellent collection of Chola, Vijayanagara, and Chera bronze idols.', 'img': 'https://example.com/napier_bronze.jpg'},
            {'title': 'Ivory Carvings', 'desc': 'Delicate and detailed ivory artwork, a specialty of Kerala craftsmanship.', 'img': 'https://example.com/napier_ivory.jpg'},
            {'title': 'Temple Chariots', 'desc': 'Intricately carved wooden models of traditional temple chariots.', 'img': 'https://example.com/napier_chariots.jpg'},
            {'title': 'Musical Instruments', 'desc': 'A collection of traditional and rare musical instruments of Kerala.', 'img': 'https://example.com/napier_music.jpg'},
            {'title': 'Traditional Kerala Costumes', 'desc': 'Display of historical garments and jewelry from the Kerala region.', 'img': 'https://example.com/napier_costumes.jpg'},
        ]
    },
    'govt_museum_art_gallery_chandigarh': {
        'name': 'Government Museum & Art Gallery',
        'city': 'Chandigarh',
        'visitors_per_year': 180000,
        'weekday_charge': 10,
        'weekend_charge': 10,
        'hours': '10:00 AM - 4:30 PM (Closed on Monday)',
        'top_exhibits': [
            {'title': 'Gandharan Sculptures', 'desc': 'A rich collection of sculptures from the Gandhara School, showing Greco-Buddhist art.', 'img': 'https://example.com/gmchd_gandhara.jpg'},
            {'title': 'Pahari Miniature Paintings', 'desc': 'Beautiful miniature paintings from the hill kingdoms of Punjab and Himachal.', 'img': 'https://example.com/gmchd_pahari.jpg'},
            {'title': 'Architecture Gallery', 'desc': 'Exhibits on the planning and architecture of Chandigarh by Le Corbusier.', 'img': 'https://example.com/gmchd_corbusier.jpg'},
            {'title': 'Decorative Arts', 'desc': 'Showcases ceramics, metalwork, and other decorative objects.', 'img': 'https://example.com/gmchd_decorative.jpg'},
            {'title': 'Portrait Gallery', 'desc': 'Historical portraits of rulers and significant figures.', 'img': 'https://example.com/gmchd_portraits.jpg'},
        ]
    },
    'dogra_art_museum_jammu': {
        'name': 'Dogra Art Museum',
        'city': 'Jammu',
        'visitors_per_year': 120000,
        'weekday_charge': 10,
        'weekend_charge': 10,
        'hours': '10:00 AM - 5:00 PM (Closed on Monday)',
        'top_exhibits': [
            {'title': 'Basohli Miniature Paintings', 'desc': 'A large and famous collection of miniature paintings from the Basohli School.', 'img': 'https://example.com/dam_basohli.jpg'},
            {'title': 'Manuscripts (Shahnameh)', 'desc': 'Rare illustrated manuscripts, including a Persian copy of the Shahnameh.', 'img': 'https://example.com/dam_shahnameh.jpg'},
            {'title': 'Terracotta Heads', 'desc': 'Ancient terracotta heads excavated from various sites.', 'img': 'https://example.com/dam_terracotta.jpg'},
            {'title': 'Metal Sculptures', 'desc': 'Bronze and metal sculptures depicting Hindu deities.', 'img': 'https://example.com/dam_metal.jpg'},
            {'title': 'Armory Section', 'desc': 'Historical arms and armour used by Dogra rulers.', 'img': 'https://example.com/dam_armory.jpg'},
        ]
    },
    'visvesvaraya_industrial_and_technological_museum': {
        'name': 'Visvesvaraya Industrial and Technological Museum',
        'city': 'Bengaluru',
        'visitors_per_year': 1100000,
        'weekday_charge': 70,
        'weekend_charge': 70,
        'hours': '9:30 AM - 6:00 PM (Open 7 days)',
        'top_exhibits': [
            {'title': 'Engine Hall', 'desc': 'Features various engines, including a steam engine and diesel locomotive.', 'img': 'https://example.com/vitm_engine.jpg'},
            {'title': 'Fun Science Gallery', 'desc': 'Interactive exhibits that demonstrate principles of physics and math playfully.', 'img': 'https://example.com/vitm_fun_science.jpg'},
            {'title': 'Space Technology Gallery', 'desc': 'Models and exhibits related to India\'s space program (ISRO).', 'img': 'https://example.com/vitm_space.jpg'},
            {'title': 'Biotechnology Revolution', 'desc': 'Exhibits covering genetics, cloning, and modern biotechnology.', 'img': 'https://example.com/vitm_biotech.jpg'},
            {'title': 'Dinosaur Model', 'desc': 'A life-size model of a massive dinosaur, popular with children.', 'img': 'https://example.com/vitm_dino.jpg'},
        ]
    },
}
# --- END CORE DATA MODEL ---


def get_db():
    conn = sqlite3.connect(db_path)
    # Set row factory to sqlite3.Row for dictionary-like access
    conn.row_factory = sqlite3.Row
    return conn

# --- Database Initialization (Unmodified) ---
def init_db():
    conn = get_db()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                museum_key TEXT NOT NULL,
                rating INTEGER NOT NULL,
                review_text TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS wishlist_status (
                user_id INTEGER NOT NULL,
                museum_key TEXT NOT NULL,
                is_visited BOOLEAN DEFAULT 0,
                PRIMARY KEY (user_id, museum_key),
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        ''')
        conn.commit()
    finally:
        conn.close()

# Initialize the database when the app starts
with app.app_context():
    init_db()

# --- Utility Functions (Unmodified) ---
def get_user(username):
    conn = get_db()
    try:
        cur = conn.execute('SELECT * FROM users WHERE username = ?', (username,))
        row = cur.fetchone()
        return row
    finally:
        conn.close()

def create_user(username, email, password_hash):
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, password_hash)
        )
        conn.commit()
    finally:
        conn.close()

def user_exists(username):
    return get_user(username) is not None

def get_user_id(username):
    user = get_user(username)
    return user['id'] if user else None

def get_museum_reviews(museum_key):
    conn = get_db()
    try:
        cur = conn.execute('''
            SELECT 
                r.rating, r.review_text, r.timestamp, u.username 
            FROM reviews r
            JOIN users u ON r.user_id = u.id
            WHERE r.museum_key = ?
            ORDER BY r.timestamp DESC
        ''', (museum_key,))
        return cur.fetchall()
    finally:
        conn.close()

def add_museum_review(user_id, museum_key, rating, review_text):
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO reviews (user_id, museum_key, rating, review_text) VALUES (?, ?, ?, ?)',
            (user_id, museum_key, rating, review_text)
        )
        conn.commit()
    finally:
        conn.close()

def get_wishlist_status(user_id, museum_key):
    conn = get_db()
    try:
        cur = conn.execute(
            'SELECT is_visited FROM wishlist_status WHERE user_id = ? AND museum_key = ?',
            (user_id, museum_key)
        )
        row = cur.fetchone()
        return row['is_visited'] if row else 0
    finally:
        conn.close()

def toggle_wishlist_status(user_id, museum_key):
    conn = get_db()
    try:
        current_status = get_wishlist_status(user_id, museum_key)
        new_status = 1 if current_status == 0 else 0
        
        conn.execute(
            'INSERT OR REPLACE INTO wishlist_status (user_id, museum_key, is_visited) VALUES (?, ?, ?)',
            (user_id, museum_key, new_status)
        )
        conn.commit()
        return new_status
    finally:
        conn.close()

# --- Authentication Decorator (Unmodified) ---
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            flash('You need to log in first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

# --- Routes (Authentication - Unmodified) ---
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect('login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        if not username or not password:
            flash('Please provide username and password.', 'error')
            return render_template('login.html')

        user = get_user(username)
        if user and check_password_hash(user['password_hash'], password):
            session['user'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password') or ''
        confirm_password = request.form.get('confirm_password') or ''

        if not username or not email or not password:
            flash('Please complete all fields', 'error')
        elif user_exists(username):
            flash('Username already exists', 'error')
        elif password != confirm_password:
            flash('Passwords do not match', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters', 'error')
        else:
            password_hash = generate_password_hash(password)
            try:
                create_user(username, email, password_hash)
                flash('Account created successfully! Please login.', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('Username already exists', 'error')

    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))


# --- Routes (Museum Functionality) ---

@app.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    search_query = request.args.get('search', '').lower()
    
    museum_list = []
    for key, data in MUSEUM_DATA.items():
        data_with_key = data.copy()
        data_with_key['key'] = key
        museum_list.append(data_with_key)
        
    if search_query:
        filtered_museums = [
            m for m in museum_list 
            if search_query in m['name'].lower() or search_query in m['city'].lower()
        ]
        museums_to_display = filtered_museums
    else:
        museums_to_display = museum_list 

    museums_to_display.sort(key=lambda m: m['name'])

    return render_template(
        'dashboard.html', 
        museums=museums_to_display, 
        search_query=search_query,
        is_quiz_selection=False # Ensure quiz link behavior is off for regular dashboard
    )

# --- NEW QUIZ SELECTION ROUTE ---
@app.route('/quiz_selection', methods=['GET'])
@login_required
def quiz_selection():
    """Renders the quiz selection page using the dashboard template."""
    museum_list = []
    for key, data in MUSEUM_DATA.items():
        data_with_key = data.copy()
        data_with_key['key'] = key
        museum_list.append(data_with_key)
    
    museum_list.sort(key=lambda m: m['name'])
    
    return render_template(
        'dashboard.html', 
        museums=museum_list, 
        search_query="",
        is_quiz_selection=True, # Flag to change link behavior in template
        quiz_message="Select a museum to generate an AI Quiz!"
    )
# --- END NEW QUIZ SELECTION ROUTE ---


@app.route('/museum/<museum_name>', methods=['GET', 'POST'])
@login_required
def museum_profile(museum_name):
    museum_key = museum_name
    museum_details = MUSEUM_DATA.get(museum_key)

    if not museum_details:
        flash('Museum profile not found.', 'error')
        return redirect(url_for('dashboard'))

    user_id = get_user_id(session['user'])
    
    if request.method == 'POST':
        if 'toggle_visited' in request.form:
            new_status = toggle_wishlist_status(user_id, museum_key)
            status_message = 'Visited' if new_status == 1 else 'Wishlist'
            flash(f'Status for {museum_details["name"]} updated to {status_message}.', 'success')
        
        elif 'review_text' in request.form:
            review_text = request.form.get('review_text') or ''
            try:
                rating = int(request.form.get('rating') or 0)
            except ValueError:
                rating = 0

            if review_text and 1 <= rating <= 5:
                add_museum_review(user_id, museum_key, rating, review_text)
                flash('Your review has been posted!', 'success')
            else:
                flash('Invalid review or rating submitted.', 'error')
        
        return redirect(url_for('museum_profile', museum_name=museum_key))

    # GET request processing
    
    # 1. Fetch the AI Summary using Gemini API
    ai_summary = get_museum_summary(museum_details['name'], museum_details['city'])

    # 2. Fetch current wishlist status
    is_visited = get_wishlist_status(user_id, museum_key)
    
    # 3. Fetch all reviews
    reviews = get_museum_reviews(museum_key)

    # 4. Extract image URLs for the gallery from the top_exhibits data
    gallery_images = [exhibit['img'] for exhibit in museum_details.get('top_exhibits', [])]

    return render_template('museum_profile.html', 
                           details=museum_details, 
                           reviews=reviews, 
                           wishlist_status=is_visited, 
                           museum_key=museum_key,
                           ai_summary=ai_summary, 
                           gallery_images=gallery_images)


# --- NEW QUIZ ROUTE ---
@app.route('/quiz/<museum_key>', methods=['GET', 'POST'])
@login_required
def quiz(museum_key):
    museum_details = MUSEUM_DATA.get(museum_key)
    if not museum_details:
        flash('Museum not found.', 'error')
        return redirect(url_for('quiz_selection'))

    museum_name = museum_details['name']
    
    if request.method == 'POST':
        # --- QUIZ SUBMISSION AND SCORING ---
        if 'current_quiz' not in session or session['current_quiz']['museum_key'] != museum_key:
            flash('Quiz session expired or mismatched. Please generate a new quiz.', 'error')
            return redirect(url_for('quiz_selection'))
            
        submitted_answers = request.form
        quiz_data = session.get('current_quiz')
        
        score = 0
        total_questions = len(quiz_data['questions'])
        results = []

        for i, q in enumerate(quiz_data['questions']):
            user_answer_key = f'q_{i}'
            user_answer = submitted_answers.get(user_answer_key)
            
            # Check if the submitted answer text matches the correct answer text
            is_correct = (user_answer == q['answer'])
            
            if is_correct:
                score += 1
            
            results.append({
                'question': q['question'],
                'user_answer': user_answer,
                'correct_answer': q['answer'],
                'is_correct': is_correct,
                'options': q['options']
            })

        # Clear the quiz data from session after scoring
        session.pop('current_quiz', None)

        return render_template('quiz.html', 
                               museum_name=museum_name, 
                               quiz_title=quiz_data['quiz_title'], 
                               score=score, 
                               total_questions=total_questions, 
                               results=results,
                               quiz_submitted=True,
                               museum_key=museum_key)

    else:
        # --- QUIZ GENERATION (GET) ---
        flash(f"Generating a new AI Quiz for {museum_name}...", 'info')
        
        # 1. Generate the quiz
        quiz_data = generate_quiz(museum_name, museum_details['city'])
        
        if not quiz_data or not quiz_data.get('questions'):
            flash('Could not generate quiz. Please try again.', 'error')
            return redirect(url_for('quiz_selection'))
        
        # 2. Store the quiz data (including answers) in the session
        quiz_data['museum_key'] = museum_key # Store key for verification
        session['current_quiz'] = quiz_data
        
        # 3. Render the quiz form
        return render_template('quiz.html', 
                               museum_name=museum_name, 
                               quiz_title=quiz_data['quiz_title'], 
                               questions=quiz_data['questions'],
                               museum_key=museum_key,
                               quiz_submitted=False)

if __name__ == '__main__':
    app.run(debug=True, port=5000)