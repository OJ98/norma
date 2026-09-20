from norma.tools.memory import AgentMemory

import time

def main():

    memory = AgentMemory()

    # Store some memories

    memory.store("The researcher requested access to the GPU cluster.")
    print("Stored memory: The researcher requested access to the GPU cluster.")
    time.sleep(3)
    memory.store("The GPU request was approved.")
    print("Stored memory: The GPU request was approved.")
    time.sleep(6)
    memory.store("The researcher requires a new dataset for the experiment.")
    print("Stored memory: The researcher requires a new dataset for the experiment.")
    time.sleep(2)
    memory.store("The new dataset is ready for use.")
    print("Stored memory: The new dataset is ready for use.")
    time.sleep(4)
    memory.store("The dataset request was denied due to insufficient resources.")
    print("Stored memory: The dataset request was denied due to insufficient resources.")
    time.sleep(1)
    memory.store("Today is Tuesday.")
    print("Stored memory: Today is Tuesday.")

    # Retrieve memories based on a query
    print("Retrieving memories related to 'GPU':")
    gpu_memories = memory.retrieve("GPU", 2)
    for mem in gpu_memories:
        print(f" - {mem}")

    print("\nRetrieving memories related to 'dataset':")
    dataset_memories = memory.retrieve("dataset", 4)
    for mem in dataset_memories:
        print(f" - {mem}")

    print("\nRetrieving memories related to 'request':")
    request_memories = memory.retrieve("request", 3)
    for mem in request_memories:
        print(f" - {mem}")

    print("\nRetrieving all memories")
    all_memories = memory.retrieve("")
    for mem in all_memories:
        print(f" - {mem}")

if __name__ == "__main__":
    main()