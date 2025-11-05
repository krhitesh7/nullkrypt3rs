.PHONY: all build local

all: local

local:
	$(eval CURRENT_COMMIT := $(shell git rev-parse --short HEAD))
	DOCKER_BUILDKIT=1 docker build --platform linux/amd64 -t conan:dev . -f Dockerfile.dev
	docker tag conan:dev sc-mum-armory.platform.internal/sharechat/conan:$(CURRENT_COMMIT)
	docker push sc-mum-armory.platform.internal/sharechat/conan:$(CURRENT_COMMIT)
