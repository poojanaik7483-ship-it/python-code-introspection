from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import importlib
import inspect  # <-- The new module added here at the top
import ollama
import uvicorn
import shutil
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# A helper function to clean up files
def remove_file(path: str):
    if os.path.exists(path):
        os.remove(path)

@app.post("/generate-readme")
async def generate_readme(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    # 1. Save uploaded file temporarily
    file_location = f"{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 2. Extract the actual source code instead of just names
    module_name = file.filename.replace(".py", "")
    try:
        mod = importlib.import_module(module_name)
        importlib.reload(mod)
        
        # Get the actual code for every custom function
        features = {}
        for name, obj in inspect.getmembers(mod):
            # Check if it is a function, has no underscores, AND was created in this specific file
            if not name.startswith("__") and inspect.isfunction(obj) and inspect.getmodule(obj) == mod:
                features[name] = inspect.getsource(obj)
                
    except Exception as e:
        return {"error": f"Could not read python file: {str(e)}"}
        
    # 3. Update the prompt to tell the AI it is reading real code
    prompt = (
        f"You are a technical writer. Create a detailed README.md file for a Python script.\n"
        f"Here is the exact source code for the custom functions in this script: {features}\n"
        "Explain what this specific code does, what parameters the functions take, and write a brief description for each one."
    )
    
    # 4. Generate text with Ollama
    response = ollama.generate(model='llama3.2', prompt=prompt)
    
    # 5. Save the AI's text to a new Markdown file
    output_name = f"{module_name}_README.md"
    with open(output_name, "w") as output_file:
        output_file.write(response['response'])
    
    # 6. Tell the server to delete both files AFTER the download completes
    background_tasks.add_task(remove_file, file_location)
    background_tasks.add_task(remove_file, output_name)
    
    # 7. Send the physical file back to the browser
    return FileResponse(output_name, media_type="text/markdown", filename=output_name)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)