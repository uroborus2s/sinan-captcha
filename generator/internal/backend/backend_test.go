package backend

import "testing"

func TestResolveNativeClick(t *testing.T) {
	spec, generator, err := Resolve("click", "native")
	if err != nil {
		t.Fatalf("expected native click backend to resolve: %v", err)
	}
	if generator == nil {
		t.Fatalf("expected generator instance")
	}
	if spec.Mode != ModeClick || spec.Backend != KindNative {
		t.Fatalf("unexpected spec: %+v", spec)
	}
	if dirs := spec.AssetDirs(); dirs["query"] != "query" || dirs["scene"] != "scene" {
		t.Fatalf("unexpected click asset dirs: %#v", dirs)
	}
}

func TestResolveNativeSlideUsesSlideDirs(t *testing.T) {
	spec, generator, err := Resolve("slide", "native")
	if err != nil {
		t.Fatalf("expected native slide backend to resolve: %v", err)
	}
	if generator == nil {
		t.Fatalf("expected generator instance")
	}
	if dirs := spec.AssetDirs(); dirs["master"] != "master" || dirs["tile"] != "tile" {
		t.Fatalf("unexpected slide asset dirs: %#v", dirs)
	}
}

func TestResolveGoCaptchaIsExplicitlyUnsupportedForNow(t *testing.T) {
	_, generator, err := Resolve("slide", "gocaptcha")
	if err == nil {
		t.Fatalf("expected unresolved gocaptcha backend to return an error")
	}
	if generator != nil {
		t.Fatalf("expected no generator when backend is unsupported")
	}
}
