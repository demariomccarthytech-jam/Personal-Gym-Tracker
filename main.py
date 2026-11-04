"""A simple, beginner-friendly gym workout tracker.

Phase 1 focuses on recording workouts, calculating basic totals, and saving
workouts locally. The functions are kept small so future features can be added
without having to rewrite the whole program.
"""

import sqlite3
from datetime import datetime
from pathlib import Path


# Store the database beside this Python file so it is easy to find and back up.
# SQLite is included with Python, so there is no extra package to install.
DATABASE_PATH = Path(__file__).with_name("workouts.db")


def connect_to_database():
    """Open the SQLite database and return a connection to it."""
    return sqlite3.connect(DATABASE_PATH)


def create_tables():
    """Create the database table the first time the program is run.

    CREATE TABLE IF NOT EXISTS keeps this safe to call every time the program
    starts: it creates the table if needed and leaves existing workouts alone.
    """
    with connect_to_database() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exercise_name TEXT NOT NULL,
                weight_lbs REAL NOT NULL,
                sets INTEGER NOT NULL,
                reps_per_set INTEGER NOT NULL,
                total_reps INTEGER NOT NULL,
                volume_lbs REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def ask_for_text(prompt):
    """Ask for text until the user enters something other than blank space."""
    while True:
        answer = input(prompt).strip()
        if answer:
            return answer
        print("Please enter a value. This field cannot be blank.")


def ask_for_number(prompt, allow_zero=False):
    """Read a number and keep asking if the input is invalid.

    Weight may be zero (for bodyweight or assisted exercise notes), but sets
    and reps must be positive numbers. This helper handles both cases.
    """
    while True:
        answer = input(prompt).strip()
        try:
            number = float(answer)
        except ValueError:
            print("Please enter a number, such as 25 or 12.5.")
            continue

        # Reject negative values, and reject zero when the field needs to be
        # greater than zero. The sets/reps fields are converted to integers
        # by their own helper below.
        if number < 0 or (number == 0 and not allow_zero):
            print("Please enter a value greater than zero.")
            continue
        return number


def ask_for_whole_number(prompt):
    """Read a positive whole number, such as a set count or rep count."""
    while True:
        answer = input(prompt).strip()
        try:
            number = int(answer)
        except ValueError:
            print("Please enter a whole number, such as 3 or 10.")
            continue

        if number <= 0:
            print("Please enter a number greater than zero.")
            continue
        return number


def collect_exercise():
    """Ask for exercise details and calculate the exercise totals."""
    print("\nEnter the exercise details:")
    exercise_name = ask_for_text("Exercise name: ")
    weight_lbs = ask_for_number("Weight lifted (lbs): ", allow_zero=True)
    sets = ask_for_whole_number("Number of sets: ")
    reps_per_set = ask_for_whole_number("Reps per set: ")

    # Total reps adds up every rep across all sets.
    total_reps = sets * reps_per_set

    # Workout volume is the lifted weight multiplied by all completed reps.
    # For example, 25 lbs x 3 sets x 10 reps = 750 lbs of volume.
    volume_lbs = weight_lbs * total_reps

    # Return all values together in a dictionary. A dictionary labels each
    # value, which makes the data easier to understand in the rest of the app.
    return {
        "exercise_name": exercise_name,
        "weight_lbs": weight_lbs,
        "sets": sets,
        "reps_per_set": reps_per_set,
        "total_reps": total_reps,
        "volume_lbs": volume_lbs,
    }


def format_weight(value):
    """Display whole-number weights without an unnecessary decimal part."""
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


def display_exercise(exercise):
    """Print one exercise in a readable, consistent format."""
    print(f"\nExercise: {exercise['exercise_name']}")
    print(f"Weight: {format_weight(exercise['weight_lbs'])} lbs")
    print(
        f"Sets and reps: {exercise['sets']} sets x "
        f"{exercise['reps_per_set']} reps"
    )
    print(f"Total reps: {exercise['total_reps']}")
    print(f"Volume: {format_weight(exercise['volume_lbs'])} lbs")


def save_exercise(exercise):
    """Save one exercise as a workout record in the database."""
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")

    # The question marks are placeholders. Passing values separately keeps
    # user input safe and lets SQLite handle text and numbers correctly.
    with connect_to_database() as connection:
        connection.execute(
            "\n"
            "            INSERT INTO workouts (\n"
            "                exercise_name, weight_lbs, sets, reps_per_set,\n"
            "                total_reps, volume_lbs, created_at\n"
            "            )\n"
            "            VALUES (?, ?, ?, ?, ?, ?, ?)\n"
            "            ",
            (
                exercise["exercise_name"],
                exercise["weight_lbs"],
                exercise["sets"],
                exercise["reps_per_set"],
                exercise["total_reps"],
                exercise["volume_lbs"],
                created_at,
            ),
        )


def add_workout():
    """Collect, show, and save an exercise entry."""
    exercise = collect_exercise()
    display_exercise(exercise)

    # Saving each exercise separately makes it simple to look up individual
    # exercise records later. A future phase can group these into sessions.
    save_exercise(exercise)
    print("Workout saved.")


def view_saved_workouts():
    """Load saved exercise records and display them newest-first."""
    with connect_to_database() as connection:
        rows = connection.execute(
            """
            SELECT exercise_name, weight_lbs, sets, reps_per_set,
                   total_reps, volume_lbs, created_at
            FROM workouts
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()

    if not rows:
        print("\nNo saved workouts yet. Choose 'Add a workout' to get started.")
        return

    # Build overall totals as we display the saved entries.
    total_reps = 0
    total_volume = 0.0
    print("\nSaved workouts")
    print("=" * 40)

    for exercise_name, weight, sets, reps, reps_total, volume, created_at in rows:
        # Convert the stored timestamp to a more familiar local display.
        saved_time = datetime.fromisoformat(created_at).astimezone()
        print(f"\n{saved_time:%Y-%m-%d %I:%M %p}")
        display_exercise(
            {
                "exercise_name": exercise_name,
                "weight_lbs": weight,
                "sets": sets,
                "reps_per_set": reps,
                "total_reps": reps_total,
                "volume_lbs": volume,
            }
        )
        total_reps += reps_total
        total_volume += volume

    # The summary totals all saved entries. In a later phase, these can be
    # grouped by a named workout session or by date.
    print("\nWorkout Summary")
    print(f"Saved Exercises: {len(rows)}")
    print(f"Total reps: {total_reps}")
    print(f"Total volume: {format_weight(total_volume)} lbs")


def show_menu():
    """Print the program's main menu."""
    print("\nPersonal Gym Tracker")
    print("1. Add a workout")
    print("2. View saved workouts")
    print("3. Exit")


def main():
    """Set up storage and run the menu until the user chooses to exit."""
    create_tables()
    print("Welcome to your Personal Gym Tracker!")

    while True:
        show_menu()
        choice = input("Choose an option (1-3): ").strip()

        if choice == "1":
            add_workout()
        elif choice == "2":
            view_saved_workouts()
        elif choice == "3":
            print("Keep up the great work. Goodbye!")
            break
        else:
            print("Please choose 1, 2, or 3.")


# This check means main() runs when this file is launched directly, but not
# when another Python file imports these functions in a future phase.
if __name__ == "__main__":
    main()
