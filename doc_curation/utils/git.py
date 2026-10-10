import logging
import os
import subprocess


def revert_new_line_only_changes(dir_path):
    env = os.environ.copy()
    logging.info("Reverting new-line-only changes in %s", dir_path)

    diff_output = subprocess.check_output(
        ["git", "diff", "HEAD", "--name-only", "--", "."],
        cwd=dir_path,
        env=env,
    ).decode("utf-8").strip()

    if not diff_output:
        logging.info("No changed files found.")
        return []

    prefix = subprocess.check_output(
        ["git", "rev-parse", "--show-prefix"],
        cwd=dir_path,
        env=env,
    ).decode("utf-8").strip()

    changed_files = diff_output.split("\n")
    reverted_files = []
    kept_files = []

    for f in changed_files:
        local_path = f[len(prefix):] if f.startswith(prefix) else f
        content_diff = subprocess.run(
            ["git", "diff", "HEAD", "--ignore-blank-lines", "--", local_path],
            cwd=dir_path,
            env=env,
            capture_output=True,
        )
        if content_diff.stdout.strip() == b"":
            subprocess.run(
                ["git", "checkout", "HEAD", "--", local_path],
                cwd=dir_path,
                env=env,
                check=True,
            )
            reverted_files.append(local_path)
        else:
            kept_files.append(local_path)

    logging.info(
        "Reverted %d new-line-only file(s); kept %d file(s) with real changes.",
        len(reverted_files),
        len(kept_files),
    )
    for f in reverted_files:
        logging.info("Reverted: %s", f)
    for f in kept_files:
        logging.debug("Kept (real changes): %s", f)

    return reverted_files


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    import sys

    default_dir = (
        "/home/vvasuki/gitland/vishvAsa/rAmAyaNam/content/kAvyam/"
        "bhAShAntaram/avadhI/tulasI-dAsaH/rAma-charita-mAnasa/"
        "goraxapura-pATha/hindy-anuvAda"
    )
    dir_path = sys.argv[1] if len(sys.argv) > 1 else default_dir
    revert_new_line_only_changes(dir_path)
