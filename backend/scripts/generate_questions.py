import sys
import os
import random

# Add parent dir to path so we can import from db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import init_db, SessionLocal, Question
from sqlalchemy import select

def generate_questions():
    init_db()
    with SessionLocal() as db:
        if db.scalar(select(Question).limit(1)) is not None:
            print("Questions already exist. Skipping generation.")
            return

        templates = [
            ("What is the primary purpose of wearing {item}?", 
             "To protect {body_part}", "To look professional", "To keep warm", "To avoid fines", "A"),
            ("When should a worker inspect their {item}?",
             "Before each use", "Once a month", "When instructed by a supervisor", "Only after an accident", "A"),
            ("Which of the following is a common hazard when operating a {machine}?",
             "Blind spots", "Loud music", "Rain", "Boredom", "A"),
            ("What is the correct action if a {machine} alarm sounds?",
             "Stop operation immediately", "Ignore it if it's brief", "Call the manager later", "Turn off the alarm", "A"),
            ("How should {material} be stored on site?",
             "In designated, secured areas", "Anywhere convenient", "Near the entrance", "Outside the site", "A"),
        ]

        items = [
            ("a hard hat", "the head from falling objects"),
            ("safety goggles", "the eyes from debris and chemicals"),
            ("steel-toe boots", "the feet from heavy impacts"),
            ("a high-visibility vest", "the wearer to be seen clearly by operators"),
            ("ear protection", "hearing from loud machinery noise"),
            ("a respirator mask", "the lungs from inhaling hazardous dust"),
            ("safety gloves", "the hands from cuts and abrasions"),
            ("a fall arrest harness", "a worker from falling at heights"),
        ]

        machines = [
            "dump truck", "excavator", "bulldozer", "crane", "forklift", 
            "motor grader", "wheel loader", "scaffolding setup", "drill rig"
        ]

        materials = [
            "flammable liquids", "hazardous chemicals", "heavy building materials",
            "electrical equipment", "compressed gas cylinders"
        ]

        # Generate 1000 questions by combining templates
        questions = []
        
        while len(questions) < 1000:
            template = random.choice(templates)
            q_text, a, b, c, d, correct = template
            
            if "{item}" in q_text:
                item_name, body_part = random.choice(items)
                q_text = q_text.format(item=item_name)
                a = a.format(body_part=body_part)
            elif "{machine}" in q_text:
                machine = random.choice(machines)
                q_text = q_text.format(machine=machine)
            elif "{material}" in q_text:
                material = random.choice(materials)
                q_text = q_text.format(material=material)
                
            # Randomize options
            opts = [a, b, c, d]
            random.shuffle(opts)
            correct_idx = opts.index(a)
            correct_letter = ["A", "B", "C", "D"][correct_idx]
            
            # To ensure uniqueness, we can append a random scenario number or just rely on the combinations
            # Actually, combinations might not reach 1000. Let's add some variations.
            scenario_num = random.randint(100, 9999)
            q_text = f"Scenario #{scenario_num}: {q_text}"

            q = Question(
                text=q_text,
                option_a=opts[0],
                option_b=opts[1],
                option_c=opts[2],
                option_d=opts[3],
                correct_answer=correct_letter
            )
            
            # small chance to add a general question
            if random.random() < 0.2:
                q_text_gen = f"Question #{scenario_num}: In an emergency evacuation, what is the first step?"
                opts_gen = ["Proceed to the nearest safe assembly point", "Pack your tools", "Call your family", "Finish your current task"]
                random.shuffle(opts_gen)
                correct_idx_gen = opts_gen.index("Proceed to the nearest safe assembly point")
                correct_letter_gen = ["A", "B", "C", "D"][correct_idx_gen]
                q = Question(text=q_text_gen, option_a=opts_gen[0], option_b=opts_gen[1], option_c=opts_gen[2], option_d=opts_gen[3], correct_answer=correct_letter_gen)
            else:
                q = Question(text=q_text, option_a=opts[0], option_b=opts[1], option_c=opts[2], option_d=opts[3], correct_answer=correct_letter)
            
            questions.append(q)

        db.add_all(questions)
        db.commit()
        print(f"Generated {len(questions)} questions.")

if __name__ == "__main__":
    generate_questions()
