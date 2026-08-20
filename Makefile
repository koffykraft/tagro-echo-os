build-EchoRuntimeFunction:
	python -m pip install -r src/aws_runtime/requirements.txt -t $(ARTIFACTS_DIR)
	cp -r src $(ARTIFACTS_DIR)/src
