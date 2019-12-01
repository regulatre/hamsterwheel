
# Copyright 2018, Brad Hein. All Rights Reserved.
# LightMQ is a lightweight in-memory queue, designed for extreme speed and simplicity.
# Specifically designed with the Raspberry Pi in mind - no disk I/O, and max size circuit breaker option.

def log (m):
    print ("LightMQ: " + m)

class LightMQ():

    def __init__(self,instanceOptions):
        log("Starting up...")

        # The directory/path where we can store things. Pickle?
        self.persistencePath = instanceOptions["persistencepath"]
        log("TODO: Load saved queue from " + self.persistencePath)

        self.maxQueueLength = instanceOptions["maxqueuelength"]

        # Define the memory queue
        self.QUEUE = []

    # Returns the queue size, which represents the number of unconsumed items that are buffered.
    def qsize(self):
        return len(self.QUEUE)

    # Peek at the next item if you want to try and process it. If processing is successful then call pop() to pop it off the stack.
    def peek(self):

        # In the event that there is no item available, return a blank string?
        if len(self.QUEUE) < 1:
            return ""

        # Let the caller peek at the next item in the FIFO queue.
        return self.QUEUE[0]

    # Pop the leftmost item off the stack and return its value. You can use just this instead of peek if you're feeling lucky. Not recommended.
    def pop(self):
        # Pop the leftmost array item off the stack. Fifo moves left. new items can be found at higher indices.
        if self.qsize() == 0:
            return ""

        self.QUEUE.pop(0)

    # Get (AND consume/pop) the next item from the queue.
    def get(self):
        if self.qsize() == 0:
            return ""

        self.QUEUE.pop(0)

    # Append the specified item to the queue FIFO
    def put(self,newItem):

        # Check and see if the queue is at capacity.
        if self.qsize() >= self.maxQueueLength:
            log("WARNING! Queue has reached its prescribed capacity of " + str(self.qsize()) + " - it's time to find out why items aren't dequeueing!")
        else:
            # Happy path - queue the item.
            self.QUEUE.append(newItem)


    def saveToDisk(self):
        log("TODO: Persist the current queue (size=" + str(self.qsize()) + " to disk!")
