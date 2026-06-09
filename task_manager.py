import os

# File to store tasks
TASKS_FILE = "tasks.txt"

def load_tasks():
    """Loads all tasks from the file."""
    if not os.path.exists(TASKS_FILE):
        return []
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines()]

def save_tasks(tasks):
    """Saves the tasks list back to the file."""
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        for task in tasks:
            f.write(task + "\n")

def add_task(task):
    """Adds a new task."""
    tasks = load_tasks()
    tasks.append(f"[ ] {task}")
    save_tasks(tasks)
    print(f"\n[+] Task '{task}' added successfully.")

def list_tasks():
    """Lists all tasks."""
    tasks = load_tasks()
    if not tasks:
        print("\n[-] No tasks found.")
        return
    print("\n=== YOUR TASKS ===")
    for idx, task in enumerate(tasks, start=1):
        print(f"{idx}. {task}")
    print("==================")

def complete_task(index):
    """Marks a task as complete."""
    tasks = load_tasks()
    if not tasks or index < 1 or index > len(tasks):
        print("\n[!] Invalid task number.")
        return
    
    # Check if already completed
    task = tasks[index - 1]
    if task.startswith("[ ]"):
        tasks[index - 1] = "[x]" + task[3:]
        save_tasks(tasks)
        print(f"\n[✓] Task {index} marked as completed.")
    else:
        print("\n[!] Task is already completed.")

def delete_task(index):
    """Deletes a task."""
    tasks = load_tasks()
    if not tasks or index < 1 or index > len(tasks):
        print("\n[!] Invalid task number.")
        return
    removed = tasks.pop(index - 1)
    save_tasks(tasks)
    print(f"\n[x] Removed task: {removed}")

def main():
    while True:
        print("\n--- TASK MANAGER CLI ---")
        print("1. List Tasks")
        print("2. Add Task")
        print("3. Mark Task as Complete")
        print("4. Delete Task")
        print("5. Exit")
        
        choice = input("\nEnter choice (1-5): ").strip()
        
        if choice == "1":
            list_tasks()
        elif choice == "2":
            task_text = input("Enter the task description: ").strip()
            if task_text:
                add_task(task_text)
            else:
                print("[!] Task description cannot be empty.")
        elif choice == "3":
            list_tasks()
            try:
                idx = int(input("Enter task number to complete: ").strip())
                complete_task(idx)
            except ValueError:
                print("[!] Please enter a valid number.")
        elif choice == "4":
            list_tasks()
            try:
                idx = int(input("Enter task number to delete: ").strip())
                delete_task(idx)
            except ValueError:
                print("[!] Please enter a valid number.")
        elif choice == "5":
            print("\nGoodbye!")
            break
        else:
            print("[!] Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
