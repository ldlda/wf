delete and replace file if youve done it.

THE OG. the GOAT. the latest and greatest.

examples\demo_workflow.py

the flow is docs -> foreach summarize -> email by flag.

also look at report_workflow, and other workflows in example.

im expanding it to the biggest and most challenging:

docs collection -> foreach summarize by person / point
|-> render markdown -> send to email
|-> foreach (collect by person -> render markdown -> lookup name -> send to email)
-> save somewhere

this exercises a lot of things.

to make shit easy lets have the docs VERY structured. Each doc is by topic(?), points by person(?), or some better system.
