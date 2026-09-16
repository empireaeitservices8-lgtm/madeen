import sys
from pathlib import Path

# Add the parent directory (backend root) to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import select
from db import init_db, SessionLocal, Question

def main():
    init_db()
    with SessionLocal() as db:
        # Check if hot_work questions exist
        existing = db.scalars(select(Question).where(Question.category == "hot_work")).all()
        if len(existing) > 0:
            print(f"Found {len(existing)} hot_work questions. Deleting to replace them.")
            for q in existing:
                db.delete(q)
            db.commit()

        # The PDF provided has exact rules. Let's create 50 exact questions based on it.
        questions_data = [
            # 1-10: Work Description & Timings
            ("What is the maximum validity duration of a Hot Work Permit?", "12 hours", "8 hours", "24 hours", "48 hours", "A"),
            ("If work is not started within 1 hour from issuing, what happens to the Hot Work Permit?", "It is cancelled", "It is extended by 1 hour", "It remains valid for 12 hours", "It requires re-authorization", "A"),
            ("Can a Hot Work Permit be extended to the next shift crew?", "Yes, indefinitely", "No, valid only for the same Shift Crew", "Yes, with verbal approval", "Only if the area is safe", "B"),
            ("How long must a Fire Watch (FW) remain on worksite after completion of job and during breaks?", "15 minutes", "30 minutes", "45 minutes", "60 minutes", "D"),
            ("What information must the Permit Receiver provide in Step 1 (Work Description)?", "Detailed description of the job or task", "Name of the HSE manager", "List of nearby hospitals", "The weather forecast", "A"),
            ("Who conducts a joint site visit to evaluate the work area?", "Receiver only", "Issuer only", "Issuer, Receiver & Area Operator", "HSE Manager and Area Operator", "C"),
            ("What is required if any gas testing is needed before issuing the permit?", "A verbal check", "A check mark (v) in the Yes box", "A photograph of the tester", "A signature from the CEO", "B"),
            ("Who is allowed to perform gas tests?", "Any worker", "Permit Receiver", "Permit Issuer", "Authorized Gas Tester", "D"),
            ("What does LEL stand for?", "Low Energy Limit", "Lower Explosive Limit", "Light Emission Level", "Life Extinguishing Level", "B"),
            ("What does IDLH stand for?", "Immediate Danger to Local Habitat", "Internal Damage from Light Heat", "Immediately Dangerous to Life or Health", "Incident Driven Loss Hazard", "C"),
            
            # 11-20: Gas Limits
            ("What is the acceptable range for Oxygen (O2) on the Hot Work Permit?", "18.0% - 19.5%", "19.5% - 20.8%", "20.8% - 21.0%", "21.0% - 23.5%", "C"),
            ("What is the maximum acceptable limit for Ammonia (NH3)?", "10 ppm", "25 ppm", "50 ppm", "100 ppm", "B"),
            ("What is the maximum acceptable limit for Hydrogen Sulfide (H2S)?", "10 ppm", "15 ppm", "20 ppm", "25 ppm", "A"),
            ("What is the maximum acceptable limit for Carbon Monoxide (CO)?", "10 ppm", "15 ppm", "25 ppm", "35 ppm", "C"),
            ("What is the acceptable level for Combustible LEL?", "0%", "< 5%", "< 10%", "< 20%", "A"),
            ("If Oxygen is less than 20.8% in the air, what does it indicate?", "The air is extremely pure", "There are other gases present or lack of oxygen", "It is safe to breathe", "The area is too cold", "B"),
            ("What is the maximum limit for Chlorine (Cl)?", "0.5 ppm", "1.0 ppm", "2.0 ppm", "5.0 ppm", "A"),
            ("What is the maximum limit for Nitric Oxide (NO)?", "10 ppm", "25 ppm", "35 ppm", "50 ppm", "B"),
            ("What is the maximum limit for Sulphur Dioxide (SO2)?", "0.5 ppm", "1.0 ppm", "2.0 ppm", "5.0 ppm", "C"),
            ("What is the acceptable threshold for Cold Stress?", ">= -8 C", "<= 45 C", "<= 0 C", ">= 10 C", "A"),

            # 21-30: Hazards & Prep
            ("What does it mean if Flammability is not 0% LEL?", "It is safe to work", "There is a hydrocarbon source", "The gas tester is faulty", "Oxygen is too high", "B"),
            ("Who has the authority to stop unsafe acts and rectify unsafe conditions?", "Only the HSE Manager", "Only the Permit Issuer", "Anyone", "Only the Area Operator", "C"),
            ("What action must be taken if continuous gas monitoring is required?", "Record results once a day", "Ensure portable gas detectors remain charged and in working order", "Leave the detector at the security gate", "Turn off the detector during breaks", "B"),
            ("What must the receiver do if the Stand by man changes?", "Cancel the permit", "Call the HSE hotline", "Make sure the new Stand by man signs the both soft & hard copy of Work Permit", "Nothing", "C"),
            ("According to the Take Two step, what should the Issuer & Receiver do before the job is started?", "Take 2 minutes to step back 2 feet and survey the area", "Take a 2-hour break", "Read the permit 2 times", "Check 2 pieces of equipment", "A"),
            ("What does 'Take Two' refer to?", "Take 2 tools to the job site", "Take 2 minutes to think through a job", "Two people must do the job", "Sign the permit in two places", "B"),
            ("Are permits valid indefinitely?", "Yes", "No, they are valid only for one (1) shift (8 or 12 hours)", "No, valid for 1 week", "No, valid until the job is done", "B"),
            ("In step 4 (Hazard Mitigation), which of the following is an 'Equipment & Area Preparation' checklist item?", "Air Horn", "Vented & Purged", "Reflective Vest", "Emergency Road Blocked", "B"),
            ("Which of the following falls under 'Energy Isolation'?", "Drained / Flushed", "Life Line", "Rotating Parts Locked (Pin/Disconnected)", "Resuscitator", "C"),
            ("Which of the following is part of 'Emergency Preparedness'?", "Approved Tag list drawing attached", "Face Shield", "Steamed", "Water Hose & Fire Hose", "D"),

            # 31-40: PPE and Steps
            ("Which of the following is NOT listed as PPE on the Hot Work Permit?", "Full Face Mask", "Half Face Mask", "Umbrella", "Rubber Boots", "C"),
            ("What type of jacket is specifically listed under PPE for welding?", "Life Jacket", "Windbreaker", "THERM JACKET (Welding)", "Rain Coat", "C"),
            ("When closing out the permit, what must the Issuer & Receiver do?", "Shred the permit", "Conduct job site inspection upon completion of work", "Renew it automatically", "Leave the site immediately", "B"),
            ("If the job is NOT completed when closing the permit, what box should be ticked?", "'Yes' for Task Completed", "'No' for Task Completed", "'Ready for Operation'", "'Housekeeping Done'", "B"),
            ("Under what conditions can a Work Permit be extended?", "Only when the job scope is changed", "Only when the conditions have NOT changed", "Any time the receiver wants", "Only if the HSE manager is present", "B"),
            ("Who must sign the Extension section if conditions remain unchanged?", "Only the Issuer", "Only the Receiver", "Authorized work permit Issuer and Receiver", "The Gas Tester", "C"),
            ("What results in immediate suspension or cancellation of the permit?", "Taking a 5-minute break", "Any non-compliance to instructions in the work permit", "Losing a pen", "Changing a lightbulb", "B"),
            ("Which gas limit is set to '< 3 ppm'?", "HF", "H2S", "CO", "SO2", "A"),
            ("Which step covers 'Making Safe'?", "Step 3", "Step 4", "Step 5", "Step 6", "C"),
            ("Which step is 'Take Two'?", "Step 5", "Step 6", "Step 7", "Step 8", "C"),

            # 41-50: Details from the Form
            ("Where must a signature be provided to authorize the Gas Test results?", "In the Take Two box", "In the Gas Test Section", "In the Work Description", "On the back of the permit", "B"),
            ("What is the requirement for interconnected equipment from adjacent areas?", "It must be ignored", "An authorized representative from the adjacent area must endorse the permit prior to issue", "It must be dismantled", "It requires a separate cold permit", "B"),
            ("What does the Standby Personnel requirement 'FW' stand for?", "First Worker", "Fire Watch", "Fast Worker", "Forward Watch", "B"),
            ("What must be done if conditions become unsafe according to the Receiver's declaration?", "Undertake to stop the work", "Call the police", "Finish the job quickly", "Ignore it if nearly done", "A"),
            ("Under Step 3 'Hazard Identification', which of the following is an example hazard?", "Combustible LEL", "Flammable Substance", "Face Shield", "Life Line", "B"),
            ("Can a hot work permit be issued if the required controller is NOT in manual (when required)?", "Yes", "No, it's a hazard mitigation requirement", "Only for 1 hour", "Yes, if the operator agrees", "B"),
            ("If a gas tester is required, what specific information must be listed?", "The brand of the tester", "The frequency at which gas tests must be repeated", "The tester's home address", "The color of the gas", "B"),
            ("What is the acceptable Heat Stress limit?", "<= 45 C", ">= 45 C", "<= 35 C", "<= 50 C", "A"),
            ("If 'Other Permits in the Same area #' is listed, what is its purpose?", "To cancel all other permits", "To identify simultaneous operations (SIMOPS) in the area", "To count how many permits were issued today", "To charge more fees", "B"),
            ("According to the permit, how many minutes are considered the 'most valuable' if they save you from injury?", "Two minutes", "Five minutes", "Ten minutes", "Sixty minutes", "A")
        ]

        # Bulk insert
        for i, q_data in enumerate(questions_data):
            text, a, b, c, d, correct = q_data
            q = Question(
                text=f"Question #{i+1}: {text}",
                option_a=a,
                option_b=b,
                option_c=c,
                option_d=d,
                correct_answer=correct,
                category="hot_work"
            )
            db.add(q)
        
        db.commit()
        print(f"Successfully generated {len(questions_data)} Hot Work Permit questions!")

if __name__ == "__main__":
    main()
