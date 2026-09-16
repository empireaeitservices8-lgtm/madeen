import sys
from pathlib import Path

# Add the parent directory (backend root) to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import select
from db import init_db, SessionLocal, Question

def main():
    init_db()
    with SessionLocal() as db:
        # Check if cold_work questions exist
        existing = db.scalars(select(Question).where(Question.category == "cold_work")).all()
        if len(existing) > 0:
            print(f"Found {len(existing)} cold_work questions. Deleting to replace them.")
            for q in existing:
                db.delete(q)
            db.commit()

        # Cold Work Permit Questions (50 variations based on the Cold Work Permit PDF)
        questions_data = [
            # 1-10: Work Description & Timings
            ("What is the maximum validity duration of a Cold Work Permit for a single shift?", "12 hours", "8 hours", "24 hours", "48 hours", "A"),
            ("If cold work is not started within 1 hour from issuing, what happens to the permit?", "It is cancelled", "It is extended by 1 hour", "It remains valid for 12 hours", "It requires re-authorization", "A"),
            ("What is the absolute maximum validity duration of a Cold Work Permit (with extensions)?", "12 hours", "24 hours", "48 hours", "72 hours", "B"),
            ("What information must be filled in Step 1 of the Cold Work Permit?", "Equipment Description & Tag Number", "Weather forecast", "Emergency contact numbers", "The worker's home address", "A"),
            ("Who conducts a joint job site inspection before issuing the Cold Work Permit?", "Permit Issuer and Receiver", "HSE Manager and CEO", "Only the Permit Receiver", "Only the Area Operator", "A"),
            ("What is the color identifier often associated with the Cold Work Permit at Ma'aden Phosphate?", "Red", "Green", "Yellow", "Blue", "B"),
            ("Under Step 2, what types of duration activities are listed?", "Normal Operation & Emergency Activity", "Hot Work & Cold Work", "Day Shift & Night Shift", "Indoor & Outdoor", "A"),
            ("If a gas testing is required for Cold Work, who is permitted to perform it?", "Permit Receiver", "Permit Issuer", "Authorized Gas Tester", "Any worker", "C"),
            ("What must be done to the 'Is Gas Test Required?' box if testing is needed?", "A cross (X) is placed in 'No'", "A check mark (v) is entered in 'Yes'", "It is left blank", "It is signed by the HSE manager", "B"),
            ("What does the 'Take Two' step mandate before starting cold work?", "Take 2 tools to the site", "Take 2 minutes to think through a job", "Assign 2 people to the task", "Perform the job twice", "B"),

            # 11-20: Gas Limits (These remain the same safety thresholds)
            ("What is the acceptable range for Oxygen (O2) on the Cold Work Permit?", "18.0% - 19.5%", "19.5% - 20.8%", "20.8% - 21.0%", "21.0% - 23.5%", "C"),
            ("What is the maximum acceptable limit for Ammonia (NH3)?", "10 ppm", "25 ppm", "50 ppm", "100 ppm", "B"),
            ("What is the maximum acceptable limit for Hydrogen Sulfide (H2S)?", "10 ppm", "15 ppm", "20 ppm", "25 ppm", "A"),
            ("What is the maximum acceptable limit for Carbon Monoxide (CO)?", "10 ppm", "15 ppm", "25 ppm", "35 ppm", "C"),
            ("What is the acceptable level for Combustible LEL?", "0%", "< 5%", "< 10%", "< 20%", "A"),
            ("What is the maximum limit for Hydrogen Fluoride (HF)?", "3 ppm", "10 ppm", "25 ppm", "50 ppm", "A"),
            ("What is the maximum limit for Sulphur Dioxide (SO2)?", "0.5 ppm", "1.0 ppm", "2.0 ppm", "5.0 ppm", "C"),
            ("What must be recorded in the Gas Tester Information section?", "Name, Badge #, Auth #", "Date of Birth", "Blood Type", "Emergency Contact", "A"),
            ("How many gas test frequency time slots are provided on the Cold Work Permit?", "3", "4", "5", "6", "C"),
            ("What is the acceptable threshold for Cold Stress?", ">= -8 C", "<= 45 C", "<= 0 C", ">= 10 C", "A"),

            # 21-30: Hazards & Prep
            ("Which of the following is listed under 'Hazard Identification' on the Cold Work Permit?", "Wall Collapsing", "Sunburn", "Food Poisoning", "Traffic Jam", "A"),
            ("Under 'Equipment & Area Preparation', which of these is a required check?", "Drained, Flushed, Steamed", "Painted", "Lubricated", "Polished", "A"),
            ("Which of the following is part of 'Energy Isolation'?", "Drained / Flushed", "Life Line", "Rotating Parts Locked (Pin/Disconnected)", "Resuscitator", "C"),
            ("Is 'Scaffolding Inspected & Tagged' a part of Equipment & Area Preparation?", "Yes", "No, it's Energy Isolation", "No, it's PPE", "No, it's Hazard Identification", "A"),
            ("Under 'Hazard Identification', which of these is an example of an environmental hazard?", "Dust/Powder Substance", "Safety Shoes", "Vented & Purged", "Blind List", "A"),
            ("Which of these items is part of 'Standby Personnel Requirement'?", "Rigger (RG)", "CEO", "Accountant", "Electrician", "A"),
            ("What does the 'Machine Guarding in place' checkbox fall under?", "Energy Isolation", "PPE", "Equipment & Area Preparation", "Hazard Identification", "C"),
            ("What must be confirmed regarding Radioactive Sources during preparation?", "They are activated", "They are isolated", "They are painted", "They are ignored", "B"),
            ("Under 'Energy Isolation', what is checked regarding the process valve?", "Process Valve Painted", "Process Valve Opened", "Process Valve Isolated", "Process Valve Removed", "C"),
            ("If work involves confined spaces, what might be checked under Equipment Prep?", "Keep Wet", "Keep Dry", "Vented & Purged", "Steamed Only", "C"),

            # 31-40: PPE and Steps
            ("Which of the following is listed as PPE on the Cold Work Permit?", "Filter Mask", "Life Jacket", "Umbrella", "Sandals", "A"),
            ("Is 'Full-Body Harness' listed as a PPE requirement on the Cold Work Permit?", "Yes", "No", "Only for Hot Work", "Only for drivers", "A"),
            ("What type of suit is listed under PPE for handling chemicals?", "Tuxedo", "Chemical Suit", "Wet Suit", "Track Suit", "B"),
            ("Which of these eye protections is explicitly listed under PPE?", "Sunglasses", "Goggles", "Contact Lenses", "Reading Glasses", "B"),
            ("Who signs Step 6 (Authorization)?", "Issuer and Receiver", "Gas Tester", "HSE Manager", "CEO", "A"),
            ("What declaration does the Permit Receiver make in Step 6?", "I accept the conditions as stated on this permit", "I declare the job is finished", "I declare the area is safe", "I declare the gas is 0%", "A"),
            ("What must the Area Operator declare in Step 6?", "Equipment and surrounding area has been made safe", "The tools are cheap", "The workers are fast", "The permit is cancelled", "A"),
            ("In Step 7 (Take Two), what is the first checklist question?", "Is the access / egress and lighting adequate?", "Is the gas tester awake?", "Are the tools new?", "Is the work over?", "A"),
            ("What must be verified regarding 'control measures' before starting the job?", "They are printed in color", "They are implemented according to formal JSA/Risk Assessment", "They are ignored if rushing", "They are emailed to the CEO", "B"),
            ("What action is taken if you answer 'NO' to any Take Two questions?", "Task shall not be performed without mitigating the new Risk", "Continue working carefully", "Call the police", "Take a break", "A"),

            # 41-50: Change/Extension and Close Out
            ("In Step 8 (Change & Extension), who must sign for Extension 1?", "Issuer and Receiver", "HSE Manager", "Gas Tester", "Security Guard", "A"),
            ("When closing out the permit (Step 9), what box does the Permit Receiver check?", "Task Completed / Housekeeping Done", "Ready for Operation", "Gas Tested", "Tools Cleaned", "A"),
            ("Who verifies the housekeeping is done in Step 9?", "Permit Receiver", "Area Operator", "Permit Issuer", "Gas Tester", "B"),
            ("What does the Permit Issuer sign for in Step 9?", "Ready For Operation", "Housekeeping Done", "Task Completed", "Gas Test Passed", "A"),
            ("Is a 'Joint Job Site Inspection' required when closing out the work permit?", "Yes", "No", "Only if there was an accident", "Only if requested by the Receiver", "A"),
            ("If a Standby-Man (SM) is required, where is their information recorded?", "Step 1", "Step 3", "Step 4", "Step 9", "C"),
            ("What happens if a worker deviates from the identified requirements?", "They must undertake to stop the work", "They get a bonus", "They finish the job first", "They call their supervisor later", "A"),
            ("Which personnel requirement is abbreviated as 'N'?", "Night Watch", "Nurse", "New Recruit", "Navigator", "B"),
            ("Which step involves checking for 'Slip/Trip' hazards?", "Step 1", "Step 2", "Step 3", "Step 4", "C"),
            ("Under Hazard Mitigation, what must be done with 'Sewer/Drains' if required?", "Covered", "Opened", "Cleaned", "Ignored", "A")
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
                category="cold_work"
            )
            db.add(q)
        
        db.commit()
        print(f"Successfully generated {len(questions_data)} Cold Work Permit questions!")

if __name__ == "__main__":
    main()
