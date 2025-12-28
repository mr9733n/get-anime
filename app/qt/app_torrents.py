

def save_torrent_wrapper(self, link, title_name, torrent_id):
    """
    Wrapper function to handle saving the torrent.
    Collects title names and links, and passes them to save_torrent_file.
    """
    try:
        sanitized_title_name = self.sanitize_filename(title_name)
        file_name = f"{sanitized_title_name}_{torrent_id}.torrent"

        self.torrent_manager.save_torrent_file(link, file_name)
        self.logger.debug("Opening torrent client ..")
    except Exception as e:
        error_message = f"Error in save_torrent_wrapper: {str(e)}"
        self.logger.error(error_message)