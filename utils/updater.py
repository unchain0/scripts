import hashlib
import os
import subprocess
import sys
import tempfile

import requests


def update_self(repo_owner: str = "unchain0", repo_name: str = "scripts") -> None:
    """Função que auxilia a atualização automática de scripts.

    Args:
        repo_owner (str, optional): Nome do proprietário do repositório. Defaults to "unchain0".
        repo_name (str, optional): Nome do repositório. Defaults to "scripts".
        script_name (str, optional): Nome do script. Defaults to None.

    Raises:
        ConnectionError: Lança erro se não conseguir buscar a versão mais recente do script.
    """
    script_name = os.path.basename(sys.argv[0])
    raw_url = (
        f"https://raw.githubusercontent.com/{repo_owner}/{repo_name}/main/{script_name}"
    )

    resp = requests.get(raw_url)
    if resp.status_code != 200:
        raise ConnectionError(
            f"Failed to fetch latest version of {script_name} from {raw_url}"
        )
    latest_hash = hashlib.sha256(resp.text.encode("utf-8")).hexdigest()

    with open(sys.argv[0], "r", encoding="utf-8") as f:
        current_hash = hashlib.sha256(f.read().encode("utf-8")).hexdigest()

    if latest_hash != current_hash:
        print(f"🔄 Atualizando {script_name}...")
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(resp.text)
            temp = f.name
        os.chmod(temp, 0o755)
        subprocess.Popen([sys.executable, temp] + sys.argv[1:])
        sys.exit(0)
    print(f"✅ {script_name} atualizado!")
